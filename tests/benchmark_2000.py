#!/usr/bin/env python3
"""RelateIQ 2,000-customer synthetic benchmark.

Scales data/generate.py to 2,000 customers (seed 42, anchor 2026-10-06),
runs the full score -> decide pipeline, and reports measured metrics.

Run from repo root:
    python3 tests/benchmark_2000.py

All results are MEASURED ON SYNTHETIC DATA, not real-world outcomes.
"""
import csv
import importlib.util
import os
import random
import re
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from app import engine  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "relateiq_gen", os.path.join(REPO, "data", "generate.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

N_CUSTOMERS = 2000
N_GENERATED = N_CUSTOMERS - 11  # 11 story customers kept, rest generated

# Action-driving signals (life-event adds score points but drives no branch).
ACTION_SIGNALS = ("dispute-open", "churn-risk", "complaint", "upsell-window")

# Signal mix for generated customers (drawn from the seeded rng, in order).
SIGNAL_MIX = [
    ("dispute-open", 0.05),
    ("churn-risk", 0.08),
    ("complaint", 0.08),
    ("life-event", 0.06),
    ("upsell-window", 0.10),
]


def assign_signals(customers):
    """Assign signals to generated customers; story customers keep theirs."""
    signals = {}
    for c in customers:
        if c["signal"] is not None:
            signals[c["customer_id"]] = [c["signal"]]
            continue
        roll = gen.rng.random()
        lo, picked = 0.0, None
        for sig, p in SIGNAL_MIX:
            if lo <= roll < lo + p:
                picked = sig
                break
            lo += p
        if picked is None:
            continue
        sigs = [picked]
        # 3% get a second, distinct signal (creates conflicts to resolve).
        if gen.rng.random() < 0.03:
            others = [s for s, _ in SIGNAL_MIX if s != picked]
            sigs.append(others[gen.rng.randrange(len(others))])
        signals[c["customer_id"]] = sigs
    return signals


def build_engine_data(customers, accounts, repayments, transactions, signals):
    accounts_by_customer = engine._index(accounts, "customer_id")
    txns_by_account = engine._index(transactions, "account_id")
    repayments_by_account = engine._index(repayments, "account_id")
    return {
        "customers": customers,
        "customers_by_id": {str(c.get("customer_id")): c for c in customers},
        "accounts": accounts,
        "accounts_by_customer": accounts_by_customer,
        "transactions": transactions,
        "txns_by_account": txns_by_account,
        "repayments": repayments,
        "repayments_by_account": repayments_by_account,
        "signals_by_customer": signals,
        "transcripts": {},
        "emails": {},
    }


def count_explainable_components(trace):
    """Number of attention components (of 6) that scored > 0, parsed from trace."""
    pts = 0
    for line in trace[1:7]:  # six attention component lines
        m = re.search(r"-> (\d+)/\d+", line)
        if m and int(m.group(1)) > 0:
            pts += 1
    return pts


def main():
    gen.rng = random.Random(gen.SEED)  # fresh deterministic stream
    gen_t0 = time.perf_counter()
    t0 = time.perf_counter()
    customers = gen.build_customers(n_generated=N_GENERATED)
    print(f"[stage] customers: {time.perf_counter()-t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    accounts = gen.build_accounts(customers)
    print(f"[stage] accounts: {time.perf_counter()-t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    repayments = gen.build_repayments(customers, accounts)
    print(f"[stage] repayments: {time.perf_counter()-t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    transactions = gen.build_transactions(customers, accounts)
    print(f"[stage] transactions: {time.perf_counter()-t0:.1f}s", flush=True)
    t0 = time.perf_counter()
    signals = assign_signals(customers)
    print(f"[stage] signals: {time.perf_counter()-t0:.1f}s", flush=True)
    t_data = time.perf_counter() - gen_t0
    t0 = time.perf_counter()

    data = build_engine_data(customers, accounts, repayments, transactions, signals)

    t1 = time.perf_counter()
    results = engine.run_pipeline(data)
    t_queue = time.perf_counter() - t1

    n = len(results)
    assert n == N_CUSTOMERS, f"expected {N_CUSTOMERS}, got {n}"

    flagged = sum(1 for r in results if r["attention"] >= 60)
    conflicting = sum(
        1 for r in results
        if sum(1 for s in r["signals"] if s in ACTION_SIGNALS) >= 2)
    dispute_hold = sum(1 for r in results if r["action"] == "dispute-hold")
    dispute_open = sum(1 for r in results if "dispute-open" in r["signals"])
    explainable = sum(1 for r in results if count_explainable_components(r["trace"]) > 0)

    dist = {}
    for r in results:
        dist[r["action"]] = dist.get(r["action"], 0) + 1

    # Audit simulation: approve every decision -> exactly one row each,
    # written to an isolated temp audit log (never touches data/audit_log.csv).
    with tempfile.TemporaryDirectory() as tmp:
        for r in results:
            engine.append_audit(tmp, {
                "timestamp": "2026-10-06T09:00:00",
                "customer_id": r["customer_id"],
                "action": r["action"],
                "attention": r["attention"],
                "opportunity": r["opportunity"],
                "reason": r["reason"],
            })
        with open(os.path.join(tmp, "audit_log.csv"), newline="",
                  encoding="utf-8") as f:
            audit_rows = list(csv.DictReader(f))
    assert len(audit_rows) == n
    assert len({row["customer_id"] for row in audit_rows}) == n

    metrics = {
        "n_customers": n,
        "n_accounts": len(accounts),
        "n_transactions": len(transactions),
        "n_repayments": len(repayments),
        "gen_seconds": round(t_data, 2),
        "queue_seconds": round(t_queue, 3),
        "pct_flagged_attention_ge_60": round(100 * flagged / n, 2),
        "pct_conflicting_signals": round(100 * conflicting / n, 2),
        "pct_dispute_hold": round(100 * dispute_hold / n, 2),
        "pct_dispute_open": round(100 * dispute_open / n, 2),
        "pct_explainable": round(100 * explainable / n, 2),
        "action_distribution": dist,
        "audit_rows_written": len(audit_rows),
    }

    print(f"customers:            {n}")
    print(f"accounts:             {len(accounts)}")
    print(f"transactions:         {len(transactions)}")
    print(f"repayments:           {len(repayments)}")
    print(f"data gen time:        {metrics['gen_seconds']}s")
    print(f"priority queue time:  {metrics['queue_seconds']}s")
    print(f"flagged (att>=60):    {metrics['pct_flagged_attention_ge_60']}%")
    print(f"conflicting signals:  {metrics['pct_conflicting_signals']}%")
    print(f"dispute-hold:         {metrics['pct_dispute_hold']}% "
          f"(dispute-open: {metrics['pct_dispute_open']}%)")
    print(f"explainable factors:  {metrics['pct_explainable']}%")
    print("action distribution:")
    for action, count in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"  {action:<20} {count:>5}  ({100 * count / n:5.2f}%)")
    print(f"audit rows written:   {len(audit_rows)} (one per decision)")

    out_path = os.path.join(REPO, "docs", "benchmark_results.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(_render_markdown(metrics))
    print(f"\nwrote {out_path}")
    return metrics


def _render_markdown(m):
    dist_rows = "\n".join(
        f"| {a} | {c} | {100 * c / m['n_customers']:.2f}% |"
        for a, c in sorted(m["action_distribution"].items(),
                           key=lambda kv: -kv[1]))
    return f"""# RelateIQ benchmark: 2,000 synthetic customers

**Status: MEASURED ON SYNTHETIC DATA.** These are timing and distribution
measurements from a synthetic portfolio, not real-world outcomes. No live
Snowflake/Cortex execution was performed.

## Methodology

- Generator: `data/generate.py`, scaled to 2,000 customers (11 story
  customers kept, 1,989 generated with the reference profile mix), seed 42,
  anchor date 2026-10-06, currency INR.
- Signal mix for generated customers: dispute-open 5%, churn-risk 8%,
  complaint 8%, life-event 6%, upsell-window 10%; 3% carry a second,
  distinct signal to create conflicts.
- Engine: `app/engine.py` `run_pipeline()` (score + decide, deterministic).
- "Flagged for attention" = Attention score >= 60 (High + Critical bands).
- "Conflicting signals" = 2+ distinct action-driving signals on one customer
  (dispute-open, churn-risk, complaint, upsell-window).
- "Explainable" = at least one of the six attention components scored > 0
  (each score ships a human-readable trace).
- Audit: every decision approved once, written to an isolated temp audit log
  (the demo `data/audit_log.csv` was untouched).

## Measured results

| Metric | Value |
|---|---|
| Customers scored | {m['n_customers']} |
| Accounts | {m['n_accounts']} |
| Transactions (90d) | {m['n_transactions']} |
| Repayments | {m['n_repayments']} |
| Synthetic data generation | {m['gen_seconds']}s |
| **Daily priority queue (score + decide, all customers)** | **{m['queue_seconds']}s** |
| Flagged for attention (Attention >= 60) | {m['pct_flagged_attention_ge_60']}% |
| Customers with conflicting signals | {m['pct_conflicting_signals']}% |
| Protected by dispute-hold | {m['pct_dispute_hold']}% (dispute-open present: {m['pct_dispute_open']}%) |
| Decisions with explainable contributing factors | {m['pct_explainable']}% |
| Audit records written (one per decision) | {m['audit_rows_written']} |

### Next-best-action distribution

| Action | Count | Share |
|---|---|---|
{dist_rows}

## Reading the numbers

- The full daily queue (score, signal merge, branch decision, draft) for a
  2,000-customer portfolio completes in seconds on commodity hardware.
- Every dispute-open customer is protected: dispute-hold fires before any
  other branch, every time (verified by the deterministic test suite).
- Conflicting signals resolve deterministically by fixed branch priority;
  no customer falls through without exactly one action and one audit row.
- Expected (not measured): earlier, correctly-toned collections should
  reduce delinquency; timed upsell offers should convert better; zero
  dispute-duns should hold because dispute-hold is a hard rule.
"""


if __name__ == "__main__":
    main()
