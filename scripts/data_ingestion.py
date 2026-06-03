"""
data_ingestion.py
----------------------------------------------------
Bluestock Fintech - Mutual Fund Analytics Capstone

Day 1 Deliverable:
- Load all datasets
- Validate data quality
- Generate summary reports
- Validate AMFI codes
- Save processed copies
- Export dataset summary

Author: Sujal Sarnobat
----------------------------------------------------
"""

from pathlib import Path
import pandas as pd
import logging
from datetime import datetime

# =====================================================
# PATH CONFIGURATION
# =====================================================

ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORT_DIR = ROOT / "reports"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# =====================================================
# LOGGING CONFIGURATION
# =====================================================

LOG_FILE = REPORT_DIR / "etl_log.txt"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# =====================================================
# DATASET REGISTRY
# =====================================================

DATASETS = {
    "fund_master": "01_fund_master.csv",
    "nav_history": "02_nav_history.csv",
    "aum_by_fund_house": "03_aum_by_fund_house.csv",
    "monthly_sip_inflows": "04_monthly_sip_inflows.csv",
    "category_inflows": "05_category_inflows.csv",
    "industry_folio_count": "06_industry_folio_count.csv",
    "scheme_performance": "07_scheme_performance.csv",
    "investor_transactions": "08_investor_transactions.csv",
    "portfolio_holdings": "09_portfolio_holdings.csv",
    "benchmark_indices": "10_benchmark_indices.csv",
}

# =====================================================
# REQUIRED COLUMNS
# =====================================================

REQUIRED_COLUMNS = {
    "fund_master": [
        "amfi_code",
        "scheme_name",
        "fund_house"
    ],

    "nav_history": [
        "amfi_code",
        "date",
        "nav"
    ],

    "investor_transactions": [
        "investor_id",
        "amfi_code",
        "amount_inr"
    ]
}


# =====================================================
# LOAD DATASET
# =====================================================

def load_dataset(name, filename):

    filepath = RAW_DIR / filename

    if not filepath.exists():
        logger.error(f"Missing file: {filepath}")
        print(f"[ERROR] Missing file: {filepath}")
        return pd.DataFrame()

    try:

        df = pd.read_csv(filepath, low_memory=False)

        logger.info(f"Loaded {filename}")

        print("\n" + "=" * 70)
        print(f"{name.upper()}")
        print("=" * 70)

        print(f"Rows      : {df.shape[0]:,}")
        print(f"Columns   : {df.shape[1]}")
        print(f"Duplicates: {df.duplicated().sum()}")

        print("\nColumns:")
        print(df.columns.tolist())

        print("\nDtypes:")
        print(df.dtypes)

        print("\nNull Values:")
        print(df.isnull().sum())

        print("\nFirst 3 Rows:")
        print(df.head(3))

        return df

    except Exception as e:

        logger.exception(f"Error loading {filename}")

        print(f"[ERROR] {filename}: {e}")

        return pd.DataFrame()


# =====================================================
# COLUMN VALIDATION
# =====================================================

def validate_columns(name, df):

    if name not in REQUIRED_COLUMNS:
        return []

    required = REQUIRED_COLUMNS[name]

    missing = list(
        set(required) - set(df.columns)
    )

    return missing


# =====================================================
# DATA QUALITY REPORT
# =====================================================

def generate_quality_report(dataframes):

    report_lines = []

    report_lines.append(
        "BLUESTOCK DATA QUALITY REPORT"
    )

    report_lines.append(
        f"Generated: {datetime.now()}"
    )

    report_lines.append("=" * 80)

    summary_rows = []

    for name, df in dataframes.items():

        if df.empty:
            continue

        rows = df.shape[0]
        cols = df.shape[1]

        missing_values = int(
            df.isnull().sum().sum()
        )

        duplicates = int(
            df.duplicated().sum()
        )

        missing_cols = validate_columns(
            name,
            df
        )

        summary_rows.append({
            "dataset": name,
            "rows": rows,
            "columns": cols,
            "missing_values": missing_values,
            "duplicates": duplicates
        })

        report_lines.append(f"\n{name}")
        report_lines.append("-" * 50)
        report_lines.append(f"Rows: {rows}")
        report_lines.append(f"Columns: {cols}")
        report_lines.append(
            f"Missing Values: {missing_values}"
        )
        report_lines.append(
            f"Duplicates: {duplicates}"
        )

        if missing_cols:
            report_lines.append(
                f"Missing Columns: {missing_cols}"
            )

    report_path = REPORT_DIR / "data_quality_report.txt"

    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))

    summary_df = pd.DataFrame(summary_rows)

    summary_df.to_csv(
        PROCESSED_DIR / "dataset_summary.csv",
        index=False
    )

    print(
        f"\n[OK] Quality report saved: {report_path}"
    )

    print(
        f"[OK] Dataset summary saved."
    )


# =====================================================
# AMFI VALIDATION
# =====================================================

def validate_amfi_codes(
        fund_master,
        nav_history):

    print("\n" + "=" * 70)
    print("AMFI CODE VALIDATION")
    print("=" * 70)

    master_codes = set(
        fund_master["amfi_code"].astype(str)
    )

    nav_codes = set(
        nav_history["amfi_code"].astype(str)
    )

    missing_codes = master_codes - nav_codes

    extra_codes = nav_codes - master_codes

    print(
        f"Fund Master Codes : {len(master_codes)}"
    )

    print(
        f"NAV History Codes : {len(nav_codes)}"
    )

    validation_df = pd.DataFrame({
        "missing_in_nav": list(missing_codes)
    })

    validation_df.to_csv(
        REPORT_DIR / "missing_amfi_codes.csv",
        index=False
    )

    if len(missing_codes) == 0:
        print(
            "\n[OK] All AMFI codes found."
        )
    else:
        print(
            f"\n[WARNING] Missing codes: {len(missing_codes)}"
        )

    if len(extra_codes):
        print(
            f"[INFO] Extra codes in NAV: {len(extra_codes)}"
        )

    logger.info(
        "AMFI validation complete"
    )


# =====================================================
# SAVE PROCESSED FILES
# =====================================================

def save_processed_files(dataframes):

    for name, df in dataframes.items():

        if df.empty:
            continue

        output_path = (
            PROCESSED_DIR /
            f"{name}_processed.csv"
        )

        df.to_csv(
            output_path,
            index=False
        )

    print(
        "\n[OK] Processed files saved."
    )


# =====================================================
# FUND MASTER SUMMARY
# =====================================================

def fund_master_summary(df):

    print("\n" + "=" * 70)
    print("FUND MASTER SUMMARY")
    print("=" * 70)

    for col in [
        "fund_house",
        "category",
        "sub_category",
        "risk_category"
    ]:

        if col in df.columns:

            print(f"\n{col.upper()}")

            print(
                df[col]
                .value_counts()
                .head(20)
            )


# =====================================================
# MAIN
# =====================================================

def main():

    print("\n")
    print("=" * 70)
    print("BLUESTOCK FINTECH")
    print("DAY 1 - DATA INGESTION PIPELINE")
    print("=" * 70)

    logger.info(
        "Data ingestion started"
    )

    dataframes = {}

    for name, filename in DATASETS.items():

        dataframes[name] = load_dataset(
            name,
            filename
        )

    generate_quality_report(
        dataframes
    )

    save_processed_files(
        dataframes
    )

    if (
        not dataframes["fund_master"].empty
        and
        not dataframes["nav_history"].empty
    ):

        validate_amfi_codes(
            dataframes["fund_master"],
            dataframes["nav_history"]
        )

    if not dataframes[
        "fund_master"
    ].empty:

        fund_master_summary(
            dataframes["fund_master"]
        )

    logger.info(
        "Data ingestion completed"
    )

    print(
        "\n[SUCCESS] Day 1 ETL completed successfully."
    )


if __name__ == "__main__":
    main()