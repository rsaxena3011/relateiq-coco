# RelateIQ - Architecture

**Author:** Ratnesh Saxena (Solo) · Snowflake CoCo CLI Hackathon 2026 (GCC Edition), PS2
**Problem:** PS2 - Customer 360 and Next Best Action Engine (digital lender / NBFC).

RelateIQ is a Customer 360 + Next Best Action Engine for a Relationship Manager (Arjun Mehta) overseeing a 2,000-borrower retail portfolio. It fuses structured account data with unstructured conversation signals and produces one decision per customer: the next best action, the reason, and a ready-to-approve outreach draft. One agent, three modular CoCo skills, two operating modes.

## System diagram

```
  +-------------------------------+    +-------------------------------+
  |  DEMO MODE (default)          |    |  LIVE MODE                    |
  |  data/customers.csv (40)      |    |  Snowflake                    |
  |  data/accounts.csv (~70)      |    |  RELATEIQ_DEMO.OPS            |
  |  data/transactions.csv (~800) |    |   CUSTOMERS, ACCOUNTS,        |
  |  data/repayments.csv (~400)   |    |   TRANSACTIONS, REPAYMENTS,   |
  |  data/call_transcripts.md     |    |   CALL_TRANSCRIPTS,           |
  |  data/support_emails.md       |    |   SUPPORT_EMAILS,             |
  |  data/audit_log.csv           |    |   ACTIONS_AUDIT               |
  +-------------------------------+    +-------------------------------+
            |                                        |
            | pandas                                 | Snowflake connector
            | (rules engine)                         | + Cortex Analyst
            v                                        |   semantic model
  +---------------------------+                      |  (03_cortex_
  |  RULES ENGINE             |                      |   analyst_model
  |  app/engine.py            |<=====================+    .yaml)
  |  score_customer()         |   same scoring & decision contract
  |  decide()                 |   regardless of data source
  +-------------+-------------+
                |
                v
  +--------------------------------------------------+
  |  SKILL 1: 360-profiler                           |
  |  SKILL 2: signal-reader                          |
  |  SKILL 3: next-best-action-orchestrator           |
  |  (.coco/skills/)                                 |
  +------------------+-------------------------------+
                     |
                     v
  +--------------------------------------------------+
  |  STREAMLIT UI  (app/main.py)                     |
  |  Tab 1 Priority Feed   (rank)                    |
  |  Tab 2 Customer 360    (diagnose)                |
  |  Tab 3 Action Queue    (decide + approve)         |
  +--------------------------------------------------+
                     |
                     v  every approved decision appended
  +--------------------------------------------------+
  |  AUDIT                                           |
  |  Demo: data/audit_log.csv                        |
  |  Live: ACTIONS_AUDIT (Snowflake, append-only)     |
  +--------------------------------------------------+
```

## Data flow: 360-profiler → signal-reader → next-best-action-orchestrator

The three CoCo skills run in a fixed pipeline. Each skill is self-contained, documented in `.coco/skills/<name>/SKILL.md`, and runnable independently.

| Stage | Skill | What happens |
|---|---|---|
| 1. Profile | `360-profiler` | Fuses structured data per customer: accounts, transactions (last 90 days), repayment history, credit utilization, tenure. Computes **Attention Score** (0-100, higher = needs attention now) and **Opportunity Score** (0-100). Every component emits a human-readable trace line. Runs over all 40 demo customers in seconds. |
| 2. Read signals | `signal-reader` | Scans unstructured sources: `call_transcripts.md` and `support_emails.md`. Extracts intent from the fixed vocabulary: `churn-risk`, `dispute-open`, `complaint`, `life-event`, `upsell-window`, `none`. A customer with `dispute-open` is flagged **DO NOT CONTACT**: no outreach is drafted, only an internal flag. |
| 3. Decide + act | `next-best-action-orchestrator` | Applies the decision branches in fixed order (see below), drafts the outreach message in Arjun Mehta's voice with real fields (name, amounts, dates), and writes every approved decision to the append-only audit table. The human approves every draft in the Action Queue; nothing is ever sent automatically. |

### Attention Score (max 100, bands: 0-29 Healthy, 30-59 Watch, 60-79 High, 80-100 Critical)

| Component | Max | Banded logic |
|---|---|---|
| Delinquency DPD | 35 | current DPD: 0→0; 1-15→12; 16-30→20; 31-60→28; 60+→35 |
| Missed history | 15 | 0→0; 1→5; 2-3→10; 4+→15 |
| Utilization stress | 15 | ≥90→15; ≥70→10; ≥50→6; else 2 |
| Credit deterioration | 10 | <600→10; <650→7; <700→4; else 0 |
| Dormancy | 10 | days since last txn: >90→10; >60→6; >30→3; else 0 |
| Unstructured signals | 15 | churn-risk→15; dispute-open→10; complaint→8; life-event→5; else 0 |

### Opportunity Score (max 100, capped)

credit_score ≥750→30 (≥700→15) · utilization <30→25 (<50→12) · missed==0→20 · tenure ≥24→15 · `upsell-window` signal→10

### Next-best-action decision branches (evaluated in order)

1. `dispute-hold` - `dispute-open` in signals. No outreach; internal flag for review. (Anchor: Amit Verma, double-charged.)
2. `churn-intervention` - `churn-risk` in signals and lifetime_value ≥ 200000. Human callback task brief. (Anchor: Vikram Rao, dormant 90+ days, high LTV.)
3. `collections-firm` - DPD > 30 or missed_payments_12m ≥ 4. Firm nudge message. (Anchor: Sneha Iyer, 5 missed, high DPD.)
4. `collections-gentle` - DPD ≥ 1. Gentle reminder. (Anchor: Divya Menon, new, first missed payment.)
5. `retention-offer` - attention ≥ 60 and DPD == 0. Personalized offer (fee waiver / rate reduction). (Anchor: Rohan Khanna, high-value, 92% utilization, fresh complaint.)
6. `upsell` - opportunity ≥ 70 and attention < 30. Pre-approved top-up offer. (Anchor: Kavya Nair, loyal, 810 score, 15% utilization.)

Anchor date: 2026-10-06 (deterministic). Seed 42 for any randomness. Currency: INR (₹).

## Dual-mode design

**Demo mode (default, zero infrastructure).** Flat files in `data/` are the source of truth: 40 customers, ~70 accounts, ~800 transactions, ~400 repayments, 10 call transcripts, 10 email threads. `app/engine.py` is a pure-Python rules engine: no LLM calls, no API keys, fully deterministic, runs on any laptop: `pip install streamlit pandas && streamlit run app/main.py`. Audit appends to `data/audit_log.csv`, created on first approved action.

**Live mode (Snowflake + Cortex Analyst).** Same UI, same skills, same scoring contract; only the data layer changes. `sql/01_schema.sql` creates `RELATEIQ_DEMO.OPS` with `CUSTOMERS`, `ACCOUNTS`, `TRANSACTIONS`, `REPAYMENTS`, `CALL_TRANSCRIPTS`, `SUPPORT_EMAILS`, `ACTIONS_AUDIT`. `sql/02_load.py` loads the `data/` files via `snowflake-connector-python` (credentials from env vars only). `sql/03_cortex_analyst_model.yaml` defines the `relateiq_model` semantic model with per-table dimensions/measures and 4-5 verified queries ("customers needing attention today", "top upsell candidates", "open disputes", "delinquency by segment"). `sql/04_audit.sql` defines `ACTIONS_AUDIT` as append-only (`action_id` autoincrement, `decided_at` default `current_timestamp`, `decided_by` default `'relateiq-agent'`) with append-only grant comments and a sample INSERT.

**Fallback behavior.** The sidebar has a Demo/Live toggle (default Demo). On selecting Live, the app reads `SNOWFLAKE_*` env vars (or `st.secrets`). On **any** connection or query failure (missing vars, bad credentials, unreachable account), the app shows a clear warning and continues in Demo mode. There is no dead-end state: a judge always sees a working product.

## Component map

```
relateiq/
├── SPEC.md                      # Build contract (this doc's source of truth)
├── README.md                    # PS2-first pitch, setup, rubric mapping
├── AGENTS.md                    # CoCo CLI operating instructions (root)
├── app/
│   ├── main.py                  # Streamlit UI: sidebar + 3 tabs (Feed / 360 / Queue)
│   └── engine.py                # score_customer(), decide() - importable standalone,
│                                #   shared by Demo and Live modes
├── sql/
│   ├── 01_schema.sql            # RELATEIQ_DEMO.OPS DDL (idempotent, types mirror CSVs)
│   ├── 02_load.py               # CSV/MD → Snowflake loader (env-var creds only)
│   ├── 03_cortex_analyst_model.yaml  # relateiq_model semantic model + verified queries
│   └── 04_audit.sql             # ACTIONS_AUDIT DDL (append-only) + sample INSERT
├── .coco/skills/
│   ├── 360-profiler/SKILL.md                # Skill 1 - nightly profiling run
│   ├── signal-reader/SKILL.md               # Skill 2 - signal scan; DO NOT CONTACT on dispute-open
│   └── next-best-action-orchestrator/SKILL.md  # Skill 3 - branches, drafting, audit
├── data/
│   ├── customers.csv            # 40 customers (Demo-mode source of truth)
│   ├── accounts.csv             # ~70 accounts (Personal Loan, Credit Card, BNPL, Two-wheeler Loan, Gold Loan)
│   ├── transactions.csv         # ~800 transactions, last 90 days (2026-07-08 to 2026-10-06)
│   ├── repayments.csv           # ~400 repayments (paid_date empty when unpaid)
│   ├── call_transcripts.md      # ~10 transcripts, Sep-Oct 2026, each ending [SIGNAL: <signal>]
│   ├── support_emails.md        # ~10 email threads, Sep 2026, each ending [SIGNAL: <signal>]
│   └── audit_log.csv            # Created on first approved action (Demo audit trail)
├── demo/
│   └── VIDEO_SCRIPT.md          # 3-5 min demo video, shot-by-shot
└── docs/
    ├── ARCHITECTURE.md          # This file
    ├── DEMO_SCRIPT.md           # 90-second narrated demo with click-by-click cues
    └── SUBMISSION_BRIEF.txt     # Prototype brief (≤1024 chars, written by coordinator)
```

## Design principles

- **One scoring contract, two backends.** `app/engine.py` is the shared brain; Demo and Live differ only in where the rows come from.
- **Unstructured data is first-class.** Call transcripts and support emails drive decisions, not just the structured repayment ledger: this is the structured/unstructured fusion PS2 asks for.
- **Never invent, never send.** The agent drafts; the human approves. No real customer is ever contacted, no credentials are ever hardcoded, every decision is audited.
- **Trust is the feature.** Every score carries its reasoning trace; every decision carries its reason; every approved action lands in an append-only audit table for compliance review.
- **Deterministic demo.** Fixed anchor date (2026-10-06), seed 42, no LLM calls in the demo path: the 90-second pitch never hangs on a slow API.
