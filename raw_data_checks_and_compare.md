# ETL Pipeline Logic — `etl_pipeline.py`

## Overview
Reads two raw CSV files from different source systems, harmonises their schemas, cleans and standardises the data, merges them into a single dataset, and appends audit metadata before writing the final output.

---

## Inputs & Outputs

- **Inputs:** `dataset_a.csv`, `dataset_b.csv` (both read as all-string columns to avoid type coercion)
- **Output:** `merged_output.csv` (1,000 rows, canonical column names, audit columns appended)

---

## Pipeline Steps

- **Step 1 — Load raw data**
  - Both CSVs are read with `dtype=str` to preserve raw values exactly as they appear
  - A hidden `_source` column is stamped on each frame (`dataset_A` / `dataset_B`) to track row origin through the merge

- **Step 2 — Column mapping**
  - Each source dataset uses different column names for the same concepts (e.g. `cust_id` vs `customer_number`, `email_addr` vs `email_address`)
  - A dictionary (`COLUMN_MAP`) maps every source column name to a single canonical target name
  - Only columns that actually exist in the dataframe are renamed — no errors on missing columns
  - After renaming, both frames are aligned to the full canonical column set; any column absent in one source is filled with an empty string

- **Step 3 — Concatenation**
  - The two aligned frames are stacked vertically into one combined dataframe
  - Row index is reset so IDs are contiguous

- **Step 4 — Null cleaning**
  - Normalises the many ways null can appear across systems: `NA`, `NULL`, `NaN`, `nan`, `none`, `None`, `N/A`, `n/a`, plus Python `None` / pandas `NaN`
  - All of these are converted to a uniform empty string `""` so downstream logic has a single blank sentinel to check against

- **Step 5 — Date standardisation**
  - Applied to three columns: `birth_date`, `account_open_date`, `last_login_date`
  - Tries 10 explicit format patterns in order (e.g. `%Y-%m-%d`, `%m/%d/%Y`, `%d-%m-%Y`, `%d-%b-%Y`, etc.)
  - Falls back to pandas' `infer_datetime_format` if none of the explicit formats match
  - All successfully parsed dates are written out in ISO format `YYYY-MM-DD`
  - Unparseable values are left as-is rather than dropped

- **Step 6 — Numeric standardisation**
  - Scans every column and attempts numeric conversion
  - Columns whose name contains `amt` or `amount` are treated as monetary and rounded to 2 decimal places
  - Other numeric-looking columns (where more than 50% of values parse successfully) are converted to integers
  - Columns that are genuinely non-numeric (e.g. names, IDs) are left unchanged
  - Empty strings are preserved as empty rather than becoming `NaN` in the output

- **Step 7 — Audit columns**
  - Six audit columns are appended to every row:

    | Column | Description |
    |---|---|
    | `audit_required_fields_missing` | Comma-separated list of required fields that are blank |
    | `audit_has_missing_required` | `YES` / `NO` flag for quick filtering |
    | `audit_missing_required_count` | Count of missing required fields |
    | `audit_source_dataset` | Which source file the row came from (`dataset_A` or `dataset_B`) |
    | `audit_load_timestamp` | UTC timestamp of when the pipeline ran |
    | `audit_row_id` | Sequential integer ID (1-based) assigned after merge |

---

## Required Fields Checked

The following fields are considered mandatory; any row missing one or more of these is flagged in the audit columns:

| Field | Description |
|---|---|
| `customer_id` | Unique customer identifier |
| `first_name` | Customer first name |
| `last_name` | Customer last name |
| `email` | Contact email address |
| `account_open_date` | Date account was opened |
| `status` | Current account status |
| `balance_amount` | Current account balance |

---

## Canonical Column Set (post-mapping)

All 20 data columns present in the final output, regardless of source:

`customer_id`, `first_name`, `last_name`, `email`, `phone`, `birth_date`, `account_open_date`, `account_type`, `status`, `balance_amount`, `deposit_amount`, `withdrawal_amount`, `credit_score`, `transaction_count`, `region`, `country_code`, `state_code`, `zip_code`, `referral_source`, `last_login_date`
