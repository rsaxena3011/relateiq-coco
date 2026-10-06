# Skill: 360-profiler

Nightly profiling run. Fuses structured account data into two scores per customer:
**Attention Score** (0–100, higher = needs attention NOW) and **Opportunity Score** (0–100).

## Trigger

- **Nightly batch:** run after 23:59 IST for all 40 customers (`data/customers.csv`).
- **Ad-hoc:** run for a single customer or subset before a review meeting or before the orchestrator evaluates them.
- **Anchor date is fixed: "today" = 2026-10-06.** Never use the system clock. DPD math uses
  `days_late = max(0, (paid_date or 2026-10-06) − due_date)`.

## Inputs

| # | Input | Demo path | Live (Snowflake) |
|---|-------|-----------|------------------|
| 1 | Customers | `data/customers.csv` | `RELATEIQ_DEMO.OPS.CUSTOMERS` |
| 2 | Accounts | `data/accounts.csv` | `RELATEIQ_DEMO.OPS.ACCOUNTS` |
| 3 | Repayments | `data/repayments.csv` | `RELATEIQ_DEMO.OPS.REPAYMENTS` |
| 4 | Transactions | `data/transactions.csv` | `RELATEIQ_DEMO.OPS.TRANSACTIONS` |
| 5 | Signals | signal-reader output for this customer | signal-reader output |

Scoring function: `app/engine.py :: score_customer(cust, accounts, repayments, txns, signals) -> (attention:int, opportunity:int, trace:list[str])`.
Seed 42 for any randomness. Currency: INR (₹).

## Scoring model — ATTENTION SCORE (max 100)

Copy these bands exactly. Each component is independent; sum and cap at 100.

| Component | Max | Bands |
|---|---|---|
| Delinquency DPD (current max DPD across open repayments) | 35 | 0 → 0; 1–15 → 12; 16–30 → 20; 31–60 → 28; 60+ → 35 |
| Missed history (`missed_payments_12m`) | 15 | 0 → 0; 1 → 5; 2–3 → 10; 4+ → 15 |
| Utilization stress (`utilization_pct`) | 15 | ≥90 → 15; ≥70 → 10; ≥50 → 6; else → 2 |
| Credit deterioration (`credit_score`) | 10 | <600 → 10; <650 → 7; <700 → 4; else → 0 |
| Dormancy (days since last txn) | 10 | >90 → 10; >60 → 6; >30 → 3; else → 0 |
| Unstructured signals | 15 | `churn-risk` → 15; `dispute-open` → 10; `complaint` → 8; `life-event` → 5; else → 0 |

**Attention bands:** 0–29 Healthy · 30–59 Watch · 60–79 High · 80–100 Critical.

## Scoring model — OPPORTUNITY SCORE (max 100)

Additive; cap at 100:

- `credit_score` ≥ 750 → 30 (else ≥ 700 → 15)
- `utilization_pct` < 30 → 25 (else < 50 → 12)
- `missed_payments_12m` == 0 → 20
- `tenure_months` ≥ 24 → 15
- `upsell-window` in signals → 10

## Procedure

1. Load `customers.csv`. For each customer:
   - Join `accounts.csv` on `customer_id`.
   - Join `repayments.csv` on `account_id`; current max DPD = max `days_late` (per anchor-date rule above).
   - Join `transactions.csv` on `account_id`; dormancy = 2026-10-06 − max(`txn_date`).
2. Get this customer's signals from the signal-reader. If the signal scan hasn't run yet,
   score with `signals=[]` and mark the row **"signals pending"** — never invent signals.
3. Call `score_customer(cust, accounts, repayments, txns, signals)`; keep the full `trace`.
4. Sort descending by attention; tie-break: opportunity desc, then `lifetime_value` desc.
5. Customers with attention ≥ 60 go to the Action Queue for the orchestrator.

## Outputs

Ranked table: `rank, customer_id, name, segment, attention (+band), opportunity, top signal`.
The `next-best-action` column is filled later by `next-best-action-orchestrator`.
Each row carries its `trace` (expandable reasoning) for the Priority Feed tab.

## Error handling

- **No repayment rows for an account** → DPD unknown: treat as 0, append trace line
  `"DPD data missing for <account_id> — treated as 0, verify manually"`.
- **No transactions in the 90-day window** → dormancy = 2026-10-06 − account `opened_date`,
  flag `"txn feed stale"`.
- **Signals not scanned yet** → score with `signals=[]`, mark "signals pending", re-score after scan.
- **Out-of-range/negative inputs** → clamp to valid range, log in trace, continue the batch.
  One bad customer must never abort the other 39.
- **Missing customer in CSV** → skip with a logged error; do not fabricate a record.

## Worked example — Sneha Iyer (delinquent → collections-firm)

Inputs: `credit_score` 585, `utilization_pct` 78, `missed_payments_12m` 5,
current DPD 45, last txn 12 days ago, `tenure_months` 30, signals: none.

**Attention:**
- DPD 45 (band 31–60) → 28/35
- Missed 5 (band 4+) → 15/15
- Utilization 78% (band ≥70) → 10/15
- Credit 585 (band <600) → 10/10
- Dormancy 12d (band ≤30) → 0/10
- Signals: none → 0/15
- **Total = 28 + 15 + 10 + 10 + 0 + 0 = 63 → High (60–79)**

**Opportunity:**
- Credit ≥700? No → 0
- Utilization <50? No (78%) → 0
- Missed == 0? No → 0
- Tenure 30 ≥ 24 → 15
- `upsell-window`? No → 0
- **Total = 15**

Result: `(attention=63, opportunity=15, trace=[...])` → sent to orchestrator;
branch 3 fires (`dpd > 30`) → `collections-firm`.
