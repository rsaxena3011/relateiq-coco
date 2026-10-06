# RelateIQ benchmark: 2,000 synthetic customers

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
- "Decisions with contributing factors" = 100% of decisions include
  contributing score factors, the winning rule/branch ID, and a human-readable
  decision trace (not a claim of full causal explainability).
- Attention score and contact eligibility are independent dimensions:
  dispute-hold can suppress outreach regardless of attention score, which is
  why the dispute-hold rate (4.90%) can differ from the flagged-for-attention
  rate (4.85%).
- The Attention >= 60 threshold is a predefined policy threshold applied
  unchanged to the seeded benchmark population, not tuned to the results.
- Action distribution (e.g. 18.9% upsell) reflects the synthetic signal mix,
  not a real lender portfolio.
- Audit: every decision approved once, written to an isolated temp audit log
  (the demo `data/audit_log.csv` was untouched).

## Measured results

| Metric | Value |
|---|---|
| Customers scored | 2000 |
| Accounts | 3430 |
| Transactions (90d) | 42349 |
| Repayments | 17613 |
| Synthetic data generation | 0.73s |
| **Daily priority queue (score + decide, all customers)** | **0.171s** |
| Flagged for attention (Attention >= 60) | 4.85% |
| Customers with conflicting signals (resolved by deterministic precedence) | 0.65% |
| Protected by dispute-hold | 4.9% (dispute-open present: 4.9%) |
| Decisions with contributing factors, rule IDs, and decision trace | 100.0% |
| Audit records written (one per decision) | 2000 |

### Next-best-action distribution

| Action | Count | Share |
|---|---|---|
| monitor | 956 | 47.80% |
| upsell | 378 | 18.90% |
| collections-firm | 265 | 13.25% |
| collections-gentle | 205 | 10.25% |
| dispute-hold | 98 | 4.90% |
| retention-offer | 51 | 2.55% |
| churn-intervention | 47 | 2.35% |

## Reading the numbers

- The full daily queue (score, signal merge, branch decision, draft) for a
  2,000-customer portfolio completes in seconds on commodity hardware.
- Every dispute-open customer is protected: dispute-hold fires before any
  other branch, every time (verified by the deterministic test suite).
- Conflicting signals resolve deterministically by fixed branch priority;
  no customer falls through without exactly one action and one audit row.
- Expected (not measured): earlier, correctly-toned collections should
  reduce delinquency; timed upsell offers should convert better. Dispute
  protection is a hard rule in the engine (verified by tests), not a measured
  business outcome.
