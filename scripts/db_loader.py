"""
db_loader.py
------------
Day 2 Tasks 4-5: Create SQLite schema and load all cleaned datasets.

Reads from : data/processed/clean_*.csv
Writes to  : data/db/bluestock_mf.db

Usage:
    python scripts/db_loader.py
"""

import sqlite3
import pandas as pd
from pathlib import Path
import logging

ROOT          = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"
DB_DIR        = ROOT / "data" / "db"
DB_PATH       = DB_DIR / "bluestock_mf.db"
SCHEMA_PATH   = ROOT / "sql" / "schema.sql"

DB_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=REPORT_DIR / "db_loader.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# ── Helper ─────────────────────────────────────────────────────────────────────

def section(title: str):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


def load_table(conn: sqlite3.Connection, csv_name: str, table_name: str,
               col_map: dict = None, date_cols: list = None) -> int:
    """
    Load a cleaned CSV into a SQLite table.
    col_map   : rename columns before insert  {old_name: new_name}
    date_cols : columns to convert to ISO date string (YYYY-MM-DD)
    """
    path = PROCESSED_DIR / csv_name
    if not path.exists():
        print(f"  [SKIP] {csv_name} not found.")
        return 0

    df = pd.read_csv(path, low_memory=False)
        # ==========================================
# FACT AUM FIX
# ==========================================

    if table_name == "fact_aum":

        if "quarter_end" not in df.columns:

            if (
                "year" in df.columns and
                "quarter" in df.columns
            ):

                quarter_map = {
                    1: "-03-31",
                    2: "-06-30",
                    3: "-09-30",
                    4: "-12-31"
                }

                df["quarter_end"] = (
                    df["year"].astype(str)
                    +
                    df["quarter"].map(
                        quarter_map
                    )
                )

            else:

                df["quarter_end"] = (
                    "2026-03-31"
                )
    if table_name == "fact_performance":

        if "as_of_date" not in df.columns:

            df["as_of_date"] = "2026-05-31"
    if table_name == "fact_transactions":

        if "tx_id" not in df.columns:

            df.insert(
                0,
                "tx_id",
                [
                    f"TX{i+1:08d}"
                    for i in range(len(df))
                ]
            )

            logger.info(
                "Generated transaction IDs"
            )
    if col_map:
        df = df.rename(columns=col_map)

    if date_cols:
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

    # Only keep columns that exist in the target table
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    db_cols = {row[1] for row in cursor.fetchall()}
    df = df[[c for c in df.columns if c in db_cols]]

    df.to_sql(table_name, conn, if_exists="append", index=False)
    print(f"  Loaded {len(df):>7,} rows → {table_name}")
    return len(df)


def build_dim_date(conn: sqlite3.Connection, nav_csv: str = "clean_nav_history.csv"):
    """Generate a complete dim_date table from the NAV date range."""
    section("BUILDING dim_date")
    path = PROCESSED_DIR / nav_csv
    if not path.exists():
        print("  [SKIP] NAV history not found, skipping dim_date.")
        return

    nav = pd.read_csv(path, usecols=["date"], low_memory=False)
    nav["date"] = pd.to_datetime(nav["date"], errors="coerce")
    min_d, max_d = nav["date"].min(), nav["date"].max()

    dates = pd.date_range(min_d, max_d, freq="D")
    dim = pd.DataFrame({"date": dates})
    dim["date_id"]      = dim["date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"]         = dim["date"].dt.year
    dim["quarter"]      = dim["date"].dt.quarter
    dim["month"]        = dim["date"].dt.month
    dim["month_name"]   = dim["date"].dt.strftime("%B")
    dim["week"]         = dim["date"].dt.isocalendar().week.astype(int)
    dim["day_of_week"]  = dim["date"].dt.dayofweek
    dim["is_weekday"]   = (dim["day_of_week"] < 5).astype(int)
    dim["date"]         = dim["date"].dt.strftime("%Y-%m-%d")

    # Mark month-end (last weekday of each month)
    dim["is_month_end"] = 0
    month_ends = (
        pd.date_range(min_d, max_d, freq="BME")
        .strftime("%Y-%m-%d")
    )
    dim.loc[dim["date"].isin(month_ends), "is_month_end"] = 1

    dim.to_sql("dim_date", conn, if_exists="append", index=False)
    print(f"  Loaded {len(dim):,} rows → dim_date  ({min_d.date()} → {max_d.date()})")

def generate_db_report(
        conn,
        tables):

    report_path = (
        REPORT_DIR /
        "database_load_report.txt"
    )

    with open(report_path, "w") as f:

        f.write(
            "BLUESTOCK DATABASE LOAD REPORT\n"
        )

        f.write("=" * 60 + "\n\n")

        for table in tables:

            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            f.write(
                f"{table:<30} {count:>10,}\n"
            )

    logger.info(
        "Database load report generated"
    )

    print(
        f"\n[OK] Report saved: "
        f"{report_path}"
    )
# ── Main ───────────────────────────────────────────────────────────────────────

def main():

    print("\n" + "=" * 60)
    print("  BLUESTOCK FINTECH — DATABASE LOADER (Day 2)")
    print("=" * 60)

    logger.info("Database loading started")

    # Remove existing DB
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"  Removed existing DB: {DB_PATH.name}")
        logger.info("Existing database removed")

    # Create connection
    conn = sqlite3.connect(DB_PATH)

    # Enable foreign keys
    conn.execute(
        "PRAGMA foreign_keys = ON;"
    )

    logger.info(
        "Foreign key constraints enabled"
    )

    # ==================================================
    # APPLY SCHEMA
    # ==================================================

    section("APPLYING SCHEMA")

    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())

    print("  Schema applied successfully.")
    logger.info("Schema applied")

    # ==================================================
    # DIMENSION TABLES
    # ==================================================

    section("LOADING DIMENSION TABLES")

    rows = load_table(
        conn,
        "clean_fund_master.csv",
        "dim_fund",
        date_cols=["launch_date"]
    )

    logger.info(
        f"dim_fund loaded ({rows:,} rows)"
    )

    # Build dim_date
    build_dim_date(conn)

    logger.info("dim_date generated")

    # ==================================================
    # FACT TABLES
    # ==================================================

    section("LOADING FACT TABLES")

    rows = load_table(
        conn,
        "clean_nav_history.csv",
        "fact_nav",
        col_map={"date": "nav_date"},
        date_cols=["nav_date"]
    )

    logger.info(
        f"fact_nav loaded ({rows:,} rows)"
    )

    rows = load_table(
        conn,
        "clean_investor_transactions.csv",
        "fact_transactions",
        date_cols=["transaction_date"]
    )

    logger.info(
        f"fact_transactions loaded ({rows:,} rows)"
    )

    rows = load_table(
        conn,
        "clean_scheme_performance.csv",
        "fact_performance",
        date_cols=["as_of_date"]
    )

    logger.info(
        f"fact_performance loaded ({rows:,} rows)"
    )

    rows = load_table(
        conn,
        "clean_portfolio_holdings.csv",
        "fact_portfolio",
        date_cols=["as_of_date"]
    )

    logger.info(
        f"fact_portfolio loaded ({rows:,} rows)"
    )

    rows = load_table(
        conn,
        "clean_aum_by_fund_house.csv",
        "fact_aum",
        date_cols=["quarter_end"]
    )

    logger.info(
        f"fact_aum loaded ({rows:,} rows)"
    )

    rows = load_table(
        conn,
        "clean_monthly_sip_inflows.csv",
        "fact_sip_industry",
        date_cols=["month"]
    )

    logger.info(
        f"fact_sip_industry loaded ({rows:,} rows)"
    )

    conn.commit()

    # ==================================================
    # VERIFICATION
    # ==================================================

    section("VERIFICATION — ROW COUNTS")

    tables = [
        "dim_fund",
        "dim_date",
        "fact_nav",
        "fact_transactions",
        "fact_performance",
        "fact_portfolio",
        "fact_aum",
        "fact_sip_industry"
    ]

    for t in tables:

        try:

            count = conn.execute(
                f"SELECT COUNT(*) FROM {t}"
            ).fetchone()[0]

            print(
                f"  {t:<30} {count:>8,} rows"
            )

        except Exception as e:

            print(
                f"  {t:<30} ERROR: {e}"
            )

            logger.error(
                f"{t}: {e}"
            )

    # ==================================================
    # REPORT
    # ==================================================

    generate_db_report(
        conn,
        tables
    )

    logger.info(
        "Database load report generated"
    )

    conn.close()

    logger.info(
        "Database loading completed"
    )

    print(
        f"\n[DONE] Database created: {DB_PATH}"
    )

    print(
        f"       Size: {DB_PATH.stat().st_size / 1024:.1f} KB"
    )

if __name__ == "__main__":
    main()