"""
live_nav_fetch.py
----------------------------------------------------
Bluestock Fintech - Mutual Fund Analytics Capstone

Day 1 Deliverable:
- Fetch live NAV history from mfapi.in
- Save individual scheme CSVs
- Save combined CSV
- Generate metadata report
- Generate fetch summary report
- Logging + Error Handling

Author: Sujal Sarnobat
----------------------------------------------------
"""

from pathlib import Path
import pandas as pd
import requests
import logging
import time

# =====================================================
# PATHS
# =====================================================

ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = ROOT / "data" / "raw"
REPORT_DIR = ROOT / "reports"

RAW_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    filename=REPORT_DIR / "live_nav_fetch.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# =====================================================
# CONFIG
# =====================================================

BASE_URL = "https://api.mfapi.in/mf/{code}"

HEADERS = {
    "User-Agent": "BluestockMFAnalytics/1.0"
}

SCHEMES = {
    125497: "HDFC_Top100_Direct",
    119551: "SBI_Bluechip_Direct",
    120503: "ICICI_Bluechip_Direct",
    118632: "Nippon_LargeCap_Direct",
    119092: "Axis_Bluechip_Direct",
    120841: "Kotak_Bluechip_Direct"
}

# =====================================================
# FETCH NAV
# =====================================================

def fetch_nav(amfi_code):

    url = BASE_URL.format(code=amfi_code)

    logger.info(f"Fetching {amfi_code}")

    for attempt in range(3):

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

            nav_data = data.get("data", [])

            if not nav_data:

                logger.warning(
                    f"No NAV data returned for {amfi_code}"
                )

                return pd.DataFrame(), {}

            df = pd.DataFrame(nav_data)

            df["amfi_code"] = amfi_code

            meta = data.get("meta", {})

            scheme_name = meta.get(
                "scheme_name",
                "Unknown"
            )

            fund_house = meta.get(
                "fund_house",
                "Unknown"
            )

            df["scheme_name"] = scheme_name
            df["fund_house"] = fund_house

            df["date"] = pd.to_datetime(
                df["date"],
                format="%d-%m-%Y",
                errors="coerce"
            )

            df["nav"] = pd.to_numeric(
                df["nav"],
                errors="coerce"
            )

            df = df.dropna(
                subset=["date", "nav"]
            )

            df = df.sort_values(
                "date"
            ).reset_index(drop=True)

            metadata = {
                "amfi_code": amfi_code,
                "scheme_name": scheme_name,
                "fund_house": fund_house,
                "rows": len(df)
            }

            logger.info(
                f"Fetched {amfi_code} successfully"
            )

            return df, metadata

        except Exception as e:

            logger.error(
                f"Attempt {attempt+1} failed for {amfi_code}: {e}"
            )

            time.sleep(2)

    logger.error(
        f"Failed after 3 attempts: {amfi_code}"
    )

    return pd.DataFrame(), {}


# =====================================================
# MAIN
# =====================================================

def main():

    print("\n" + "=" * 70)
    print("BLUESTOCK FINTECH")
    print("LIVE NAV FETCH PIPELINE")
    print("=" * 70)

    metadata_rows = []
    all_dataframes = []

    for code, label in SCHEMES.items():

        print(f"\nFetching {label}...")

        df, metadata = fetch_nav(code)

        if df.empty:

            print(
                f"[FAILED] {label}"
            )

            continue

        output_file = (
            RAW_DIR /
            f"live_nav_{label}.csv"
        )

        df.to_csv(
            output_file,
            index=False
        )

        print(
            f"[OK] Saved: {output_file.name}"
        )

        metadata_rows.append(metadata)

        all_dataframes.append(df)

        time.sleep(0.5)

    # =================================================
    # COMBINED FILE
    # =================================================

    if all_dataframes:

        combined_df = pd.concat(
            all_dataframes,
            ignore_index=True
        )

        combined_file = (
            RAW_DIR /
            "live_nav_all_schemes.csv"
        )

        combined_df.to_csv(
            combined_file,
            index=False
        )

        print(
            f"\n[OK] Combined file saved: "
            f"{combined_file.name}"
        )

    # =================================================
    # METADATA REPORT
    # =================================================

    if metadata_rows:

        metadata_df = pd.DataFrame(
            metadata_rows
        )

        metadata_df.to_csv(
            REPORT_DIR /
            "live_nav_metadata.csv",
            index=False
        )

        metadata_df.to_csv(
            REPORT_DIR /
            "nav_fetch_summary.csv",
            index=False
        )

        print(
            "[OK] Metadata report generated."
        )

    logger.info(
        "Live NAV fetch completed"
    )

    print(
        "\n[SUCCESS] NAV Fetch Completed."
    )


if __name__ == "__main__":
    main()