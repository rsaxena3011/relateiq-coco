#!/usr/bin/env python3
"""RelateIQ — load local data files into Snowflake (Live mode).

Loads data/*.csv (customers, accounts, transactions, repayments, audit_log),
data/call_transcripts.md and data/support_emails.md into RELATEIQ_DEMO.OPS.

Credentials ONLY from environment (no hardcoded secrets, no prompts):
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
    SNOWFLAKE_WAREHOUSE, SNOWFLAKE_ROLE

Usage:  python sql/02_load.py
"""
from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"

DB = "RELATEIQ_DEMO"
SCHEMA = "OPS"

TABLE_COLUMNS = {
    "CUSTOMERS": (
        "customer_id", "name", "segment", "region", "tenure_months", "credit_score",
        "credit_limit", "utilization_pct", "missed_payments_12m", "avg_days_late",
        "products_held", "lifetime_value", "behavior_profile", "contact_email", "contact_phone",
    ),
    "ACCOUNTS": (
        "account_id", "customer_id", "product_type", "sanctioned_limit",
        "outstanding", "status", "opened_date",
    ),
    "TRANSACTIONS": (
        "txn_id", "account_id", "txn_date", "amount", "category", "channel",
    ),
    "REPAYMENTS": (
        "repayment_id", "account_id", "due_date", "paid_date",
        "amount_due", "amount_paid", "days_late",
    ),
}

# Date columns (opened_date, txn_date, due_date, paid_date) are bound as
# 'YYYY-MM-DD' strings; Snowflake auto-casts them to DATE on INSERT.


def get_connection():
    """Build a Snowflake connection strictly from env vars."""
    required = {
        "SNOWFLAKE_ACCOUNT": os.environ.get("SNOWFLAKE_ACCOUNT"),
        "SNOWFLAKE_USER": os.environ.get("SNOWFLAKE_USER"),
        "SNOWFLAKE_PASSWORD": os.environ.get("SNOWFLAKE_PASSWORD"),
        "SNOWFLAKE_WAREHOUSE": os.environ.get("SNOWFLAKE_WAREHOUSE"),
        "SNOWFLAKE_ROLE": os.environ.get("SNOWFLAKE_ROLE"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise SystemExit(
            "Missing required env vars (no defaults, no fallbacks): "
            + ", ".join(missing)
        )
    import snowflake.connector

    return snowflake.connector.connect(
        account=required["SNOWFLAKE_ACCOUNT"],
        user=required["SNOWFLAKE_USER"],
        password=required["SNOWFLAKE_PASSWORD"],
        warehouse=required["SNOWFLAKE_WAREHOUSE"],
        role=required["SNOWFLAKE_ROLE"],
        database=DB,
        schema=SCHEMA,
    )


def empty_to_none(value: str) -> str | None:
    """Normalize empty CSV cells to NULL."""
    return None if value.strip() == "" else value.strip()


def load_table(cur, table: str, csv_path: Path) -> int:
    """Load a CSV into a table with executemany. Idempotent via DELETE first."""
    columns = TABLE_COLUMNS[table]
    rows: list[tuple] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for rec in reader:
            row = []
            for col in columns:
                val = empty_to_none(rec[col])
                row.append(val)
            rows.append(tuple(row))
    cur.execute(f"DELETE FROM {table}")
    placeholders = ", ".join(["%s"] * len(columns))
    cur.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows
    )
    return len(rows)


def split_unstructured_docs(md_path: Path) -> list[tuple[str, str]]:
    """Split a multi-customer markdown file into (customer_id, doc_md) blocks.

    Each block starts with a level-2/3 heading like '## CUST-007 — Rohan Khanna'.
    """
    text = md_path.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^##\s+", text)
    out: list[tuple[str, str]] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = re.match(r"(CUST-\d{3})\b", block)
        if not m:
            continue
        out.append((m.group(1), "## " + block))
    return out


def load_unstructured(cur, table: str, md_path: Path) -> int:
    """Load per-customer markdown docs into a two-column table (idempotent)."""
    docs = split_unstructured_docs(md_path)
    cur.execute(f"DELETE FROM {table}")
    cur.executemany(
        f"INSERT INTO {table} (customer_id, {'transcript_md' if table == 'CALL_TRANSCRIPTS' else 'thread_md'}) "
        "VALUES (%s, %s)",
        docs,
    )
    return len(docs)


def main() -> None:
    for expected in (
        "customers.csv", "accounts.csv", "transactions.csv",
        "repayments.csv", "call_transcripts.md", "support_emails.md",
    ):
        if not (DATA_DIR / expected).exists():
            raise SystemExit(f"Missing required data file: {DATA_DIR / expected}")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            counts = {}
            for table, fname in (
                ("CUSTOMERS", "customers.csv"),
                ("ACCOUNTS", "accounts.csv"),
                ("TRANSACTIONS", "transactions.csv"),
                ("REPAYMENTS", "repayments.csv"),
            ):
                counts[table] = load_table(cur, table, DATA_DIR / fname)
            counts["CALL_TRANSCRIPTS"] = load_unstructured(
                cur, "CALL_TRANSCRIPTS", DATA_DIR / "call_transcripts.md"
            )
            counts["SUPPORT_EMAILS"] = load_unstructured(
                cur, "SUPPORT_EMAILS", DATA_DIR / "support_emails.md"
            )
        conn.commit()
    finally:
        conn.close()

    print("Loaded into RELATEIQ_DEMO.OPS:")
    for table, n in counts.items():
        print(f"  {table}: {n} rows")


if __name__ == "__main__":
    main()
