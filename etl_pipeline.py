"""
etl_pipeline.py
---------------
ETL pipeline that reads two raw CSV files, maps columns to canonical names,
cleans nulls, standardizes dates and numerics, merges, and adds audit columns.

Prerequisites:
    Run generate_data.py first to produce dataset_a.csv and dataset_b.csv.

Inputs:
    dataset_a.csv
    dataset_b.csv

Outputs:
    merged_output.xlsx  (sheets: Merged_Data, Column_Mapping, Required_Fields)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG — INPUT PATHS
# ═══════════════════════════════════════════════════════════════════════════════
_HERE   = Path(__file__).parent
INPUT_A = str(_HERE / "dataset_a.csv")
INPUT_B = str(_HERE / "dataset_b.csv")
OUTPUT  = str(_HERE / "merged_output.csv")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. COLUMN MAPPING DICTIONARY  (source_col → canonical target name)
# ═══════════════════════════════════════════════════════════════════════════════
COLUMN_MAP = {
    # Dataset A
    "cust_id":           "customer_id",
    "first_nm":          "first_name",
    "last_nm":           "last_name",
    "email_addr":        "email",
    "ph_number":         "phone",
    "dob":               "birth_date",
    "acct_open_dt":      "account_open_date",
    "acct_type":         "account_type",
    "acct_status":       "status",
    "bal_amt":           "balance_amount",
    "dep_amt":           "deposit_amount",
    "wthd_amt":          "withdrawal_amount",
    "credit_scr":        "credit_score",
    "num_txns":          "transaction_count",
    "region":            "region",
    "cntry_cd":          "country_code",
    "state_cd":          "state_code",
    "zip":               "zip_code",
    "referral_src":      "referral_source",
    "last_login_dt":     "last_login_date",
    # Dataset B
    "customer_number":   "customer_id",
    "fname":             "first_name",
    "lname":             "last_name",
    "email_address":     "email",
    "telephone":         "phone",
    "date_of_birth":     "birth_date",
    "open_date":         "account_open_date",
    "account_category":  "account_type",
    "account_state":     "status",
    "balance_amount":    "balance_amount",
    "deposit_amount":    "deposit_amount",
    "withdrawal_amount": "withdrawal_amount",
    "credit_rating":     "credit_score",
    "txn_count":         "transaction_count",
    "geo_region":        "region",
    "country":           "country_code",
    "state":             "state_code",
    "postal_code":       "zip_code",
    "lead_source":       "referral_source",
    "last_access_date":  "last_login_date",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. REQUIRED FIELDS DICTIONARY
# ═══════════════════════════════════════════════════════════════════════════════
REQUIRED_FIELDS = {
    "customer_id":       "Unique customer identifier",
    "first_name":        "Customer first name",
    "last_name":         "Customer last name",
    "email":             "Contact email address",
    "account_open_date": "Date account was opened",
    "status":            "Current account status",
    "balance_amount":    "Current account balance",
}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DATE COLUMNS
# ═══════════════════════════════════════════════════════════════════════════════
DATE_COLUMNS = ["birth_date", "account_open_date", "last_login_date"]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TRANSFORMATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def apply_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
    rename = {src: tgt for src, tgt in COLUMN_MAP.items() if src in df.columns}
    return df.rename(columns=rename)


def clean_nulls(df: pd.DataFrame) -> pd.DataFrame:
    null_strings = {"NA", "NULL", "NaN", "nan", "none", "None", "N/A", "n/a"}
    df = df.where(df.notna(), other="")
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(
            lambda v: "" if (isinstance(v, str) and v.strip() in null_strings) else v
        )
    return df


def standardize_dates(df: pd.DataFrame) -> pd.DataFrame:
    date_fmts = (
        "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d",
        "%d/%m/%Y", "%Y%m%d",   "%m-%d-%Y", "%d.%m.%Y",
        "%d-%b-%Y", "%b-%d-%Y",
    )
    for col in DATE_COLUMNS:
        if col not in df.columns:
            continue
        def parse(v):
            if v == "" or pd.isna(v):
                return ""
            for fmt in date_fmts:
                try:
                    return datetime.strptime(str(v).strip(), fmt).strftime("%Y-%m-%d")
                except ValueError:
                    pass
            try:
                return pd.to_datetime(str(v), infer_datetime_format=True).strftime("%Y-%m-%d")
            except Exception:
                return str(v)
        df[col] = df[col].apply(parse)
    return df


def standardize_numerics(df: pd.DataFrame) -> pd.DataFrame:
    amount_keywords = ("amt", "amount")
    for col in df.columns:
        is_amount = any(kw in col.lower() for kw in amount_keywords)
        converted = pd.to_numeric(df[col].replace("", np.nan), errors="coerce")
        if converted.notna().sum() == 0:
            continue
        if is_amount:
            df[col] = converted.apply(lambda v: round(float(v), 2) if pd.notna(v) else "")
        elif converted.notna().mean() > 0.5:
            df[col] = converted.apply(lambda v: int(round(v)) if pd.notna(v) else "")
    return df


def add_audit_columns(df: pd.DataFrame) -> pd.DataFrame:
    req_cols = list(REQUIRED_FIELDS.keys())

    def missing_fields(row):
        missing = [f for f in req_cols if f in row.index and str(row[f]).strip() == ""]
        return ", ".join(missing) if missing else ""

    df["audit_required_fields_missing"] = df.apply(missing_fields, axis=1)
    df["audit_has_missing_required"]    = df["audit_required_fields_missing"].apply(
                                              lambda v: "YES" if v else "NO")
    df["audit_missing_required_count"]  = df["audit_required_fields_missing"].apply(
                                              lambda v: len(v.split(", ")) if v else 0)
    df["audit_source_dataset"]          = df.pop("_source")
    df["audit_load_timestamp"]          = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    df["audit_row_id"]                  = range(1, len(df) + 1)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline():
    print("=" * 65)
    print("  ETL PIPELINE START")
    print("=" * 65)

    # --- Load ---
    print(f"\n[1] Reading input files …")
    raw_a = pd.read_csv(INPUT_A, dtype=str)
    raw_b = pd.read_csv(INPUT_B, dtype=str)
    raw_a["_source"] = "dataset_A"
    raw_b["_source"] = "dataset_B"
    print(f"    Dataset A: {raw_a.shape}  |  Dataset B: {raw_b.shape}")

    # --- Map columns ---
    print("[2] Applying column mapping …")
    mapped_a = apply_column_mapping(raw_a)
    mapped_b = apply_column_mapping(raw_b)

    # Align both to the full canonical column set
    canonical_cols = list(dict.fromkeys(COLUMN_MAP.values())) + ["_source"]
    for col in canonical_cols:
        if col not in mapped_a.columns:
            mapped_a[col] = ""
        if col not in mapped_b.columns:
            mapped_b[col] = ""
    mapped_a = mapped_a[canonical_cols]
    mapped_b = mapped_b[canonical_cols]

    # --- Merge ---
    print("[3] Concatenating datasets …")
    combined = pd.concat([mapped_a, mapped_b], ignore_index=True)
    print(f"    Combined shape: {combined.shape}")

    # --- Clean ---
    print("[4] Cleaning NA / NULL values …")
    combined = clean_nulls(combined)

    print("[5] Standardizing date columns …")
    combined = standardize_dates(combined)

    print("[6] Standardizing numeric columns …")
    combined = standardize_numerics(combined)

    # --- Audit ---
    print("[7] Adding audit columns …")
    combined = add_audit_columns(combined)

    # --- Summary ---
    total      = len(combined)
    has_issues = (combined["audit_has_missing_required"] == "YES").sum()
    print(f"\n{'─'*65}")
    print(f"  Total rows          : {total}")
    print(f"  Rows with issues    : {has_issues}  ({100*has_issues/total:.1f}%)")
    print(f"  Rows clean          : {total - has_issues}")
    print(f"{'─'*65}")

    # --- Save ---
    combined.to_csv(OUTPUT, index=False)

    print(f"\n  Output saved → {OUTPUT}")
    print("=" * 65)
    print("  ETL PIPELINE COMPLETE")
    print("=" * 65)

    return combined


if __name__ == "__main__":
    df = run_pipeline()

    print("\nSample rows with missing required fields:")
    sample = df[df["audit_has_missing_required"] == "YES"][
        ["customer_id","first_name","last_name","email",
         "audit_required_fields_missing","audit_missing_required_count"]
    ].head(10)
    print(sample.to_string(index=False))
