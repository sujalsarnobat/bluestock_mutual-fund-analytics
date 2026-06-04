"""
data_cleaning.py
----------------
Day 2 Tasks 1-3: Clean all 10 raw datasets and save to data/processed/.

Cleaning rules per dataset:
  nav_history        — parse dates, sort, forward-fill missing NAV, remove dupes, validate NAV > 0
  investor_txns      — standardise tx type, validate amount > 0, fix dates, check KYC values
  scheme_performance — validate numeric returns, flag bad Sharpe/expense ratios
  All others         — basic null check, type casting, deduplication

Usage:
    python scripts/data_cleaning.py
"""

import re
import numpy as np
import pandas as pd
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
RAW_DIR       = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ── Helper ─────────────────────────────────────────────────────────────────────

def save(df: pd.DataFrame, name: str) -> Path:
    out = PROCESSED_DIR / name
    df.to_csv(out, index=False)
    print(f"    Saved → {name}  ({len(df):,} rows)")
    return out


def section(title: str):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# ── 1. NAV History ─────────────────────────────────────────────────────────────

def clean_nav_history() -> pd.DataFrame:
    section("CLEANING: nav_history")
    df = pd.read_csv(RAW_DIR / "02_nav_history.csv", low_memory=False)
    print(f"  Raw shape : {df.shape}")

    # Parse date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    null_dates = df["date"].isna().sum()
    if null_dates:
        print(f"  [WARN] {null_dates} unparseable dates dropped.")
    df = df.dropna(subset=["date"])

    # Numeric NAV
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    # Remove duplicates
    before = len(df)
    df = df.drop_duplicates(subset=["amfi_code", "date"])
    print(f"  Duplicates removed : {before - len(df)}")

    # Sort
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    # Forward-fill missing NAV per scheme (weekends / holidays)
    full_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="B")  # business days
    filled_dfs = []
    for code, grp in df.groupby("amfi_code"):
        grp = grp.set_index("date").reindex(full_dates)
        grp["amfi_code"] = code
        grp["nav"] = grp["nav"].ffill()
        grp = grp.reset_index().rename(columns={"index": "date"})
        filled_dfs.append(grp)

    df = pd.concat(filled_dfs, ignore_index=True)

    # Validate NAV > 0
    invalid = df[df["nav"] <= 0]
    if len(invalid):
        print(f"  [WARN] {len(invalid)} rows with NAV ≤ 0 removed.")
        df = df[df["nav"] > 0]

    # Compute daily return %
    df = df.sort_values(["amfi_code", "date"])
    df["daily_return_pct"] = df.groupby("amfi_code")["nav"].pct_change() * 100

    print(f"  Clean shape : {df.shape}")
    return save(df, "clean_nav_history.csv")


# ── 2. Investor Transactions ───────────────────────────────────────────────────

TX_TYPE_MAP = {
    "sip":        "SIP",
    "lumpsum":    "Lumpsum",
    "lump sum":   "Lumpsum",
    "redemption": "Redemption",
    "redeem":     "Redemption",
}

VALID_KYC = {"Verified", "Pending"}


def clean_investor_transactions() -> pd.DataFrame:
    section("CLEANING: investor_transactions")
    df = pd.read_csv(RAW_DIR / "08_investor_transactions.csv", low_memory=False)
    print(f"  Raw shape : {df.shape}")

    # Standardise transaction_type
    df["transaction_type"] = (
        df["transaction_type"]
        .astype(str).str.strip().str.lower()
        .map(TX_TYPE_MAP)
        .fillna(df["transaction_type"])
    )
    unknown_types = df[~df["transaction_type"].isin(["SIP","Lumpsum","Redemption"])]["transaction_type"].unique()
    if len(unknown_types):
        print(f"  [WARN] Unknown tx types: {unknown_types}")

    # Parse dates
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date"])

    # Validate amount > 0
    df["amount_inr"] = pd.to_numeric(df["amount_inr"], errors="coerce")
    neg = (df["amount_inr"] <= 0).sum()
    if neg:
        print(f"  [WARN] {neg} rows with amount ≤ 0 removed.")
    df = df[df["amount_inr"] > 0]

    # KYC check
    invalid_kyc = df[~df["kyc_status"].isin(VALID_KYC)]
    if len(invalid_kyc):
        print(f"  [WARN] {len(invalid_kyc)} rows with invalid KYC status.")

    # Dedup
    before = len(df)
    df = df.drop_duplicates()
    print(f"  Duplicates removed : {before - len(df)}")

    print(f"  Clean shape : {df.shape}")
    return save(df, "clean_investor_transactions.csv")


# ── 3. Scheme Performance ──────────────────────────────────────────────────────

def clean_scheme_performance() -> pd.DataFrame:
    section("CLEANING: scheme_performance")
    df = pd.read_csv(RAW_DIR / "07_scheme_performance.csv", low_memory=False)
    print(f"  Raw shape : {df.shape}")

    numeric_cols = [
        "return_1yr_pct", "return_3yr_pct", "return_5yr_pct",
        "alpha", "beta", "sharpe_ratio", "sortino_ratio",
        "std_dev_ann_pct", "max_drawdown_pct", "expense_ratio_pct",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Flag suspicious Sharpe ratios (outside -3 to +5 is unusual)
    if "sharpe_ratio" in df.columns:
        flagged = df[df["sharpe_ratio"] < -3]
        if len(flagged):
            print(f"  [FLAG] {len(flagged)} funds with Sharpe < -3: {flagged['amfi_code'].tolist()}")

    # Validate expense ratio range
    if "expense_ratio_pct" in df.columns:
        out_of_range = df[~df["expense_ratio_pct"].between(0.05, 2.5)]
        if len(out_of_range):
            print(f"  [FLAG] {len(out_of_range)} funds with expense_ratio outside [0.05%, 2.5%]:")
            print(f"         {out_of_range[['amfi_code','expense_ratio_pct']].to_string()}")

    print(f"  Clean shape : {df.shape}")
    return save(df, "clean_scheme_performance.csv")


# ── 4. Generic cleaner for remaining datasets ──────────────────────────────────

GENERIC_DATASETS = {
    "01_fund_master.csv":          "clean_fund_master.csv",
    "03_aum_by_fund_house.csv":    "clean_aum_by_fund_house.csv",
    "04_monthly_sip_inflows.csv":  "clean_monthly_sip_inflows.csv",
    "05_category_inflows.csv":     "clean_category_inflows.csv",
    "06_industry_folio_count.csv": "clean_industry_folio_count.csv",
    "09_portfolio_holdings.csv":   "clean_portfolio_holdings.csv",
    "10_benchmark_indices.csv":    "clean_benchmark_indices.csv",
}


def clean_generic(raw_name: str, clean_name: str) -> None:
    section(f"CLEANING: {raw_name}")
    path = RAW_DIR / raw_name
    if not path.exists():
        print(f"  [MISSING] {path}")
        return

    df = pd.read_csv(path, low_memory=False)
    print(f"  Raw shape : {df.shape}")

    # Parse any column named *date* or *month*
    for col in df.columns:
        if "date" in col.lower():
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif col.lower() == "month":
            df[col] = pd.to_datetime(df[col], format="%Y-%m", errors="coerce")

    # Remove full-row duplicates
    before = len(df)
    df = df.drop_duplicates()
    if before - len(df):
        print(f"  Duplicates removed : {before - len(df)}")

    # Report nulls
    nulls = df.isnull().sum()
    nulls = nulls[nulls > 0]
    if not nulls.empty:
        print(f"  Null counts:\n{nulls.to_string()}")

    print(f"  Clean shape : {df.shape}")
    save(df, clean_name)


# ── Master runner ──────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  BLUESTOCK FINTECH — DATA CLEANING  (Day 2)")
    print("="*60)

    clean_nav_history()
    clean_investor_transactions()
    clean_scheme_performance()

    for raw_name, clean_name in GENERIC_DATASETS.items():
        clean_generic(raw_name, clean_name)

    print("\n[DONE] All datasets cleaned and saved to data/processed/")


if __name__ == "__main__":
    main()