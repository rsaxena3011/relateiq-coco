# AGENTS.md — RelateIQ CoCo CLI Operating Instructions

RelateIQ: Customer 360 + Next Best Action Engine for a digital lender (NBFC).
Snowflake CoCo CLI Hackathon 2026 (GCC Edition), Problem Statement PS2. Author: Ratnesh Saxena (Solo).

## Setup — demo first

```bash
cd ~/workspace/snowflake-coco-hackathon
pip install streamlit pandas          # ONLY dependencies
streamlit run app/main.py             # demo mode (default)
```

Demo mode uses the CSV/markdown files under `data/` and `data/audit_log.csv`. No API keys,
no credentials, no network calls. **Always get the demo running before touching live mode.**

Live mode: set `SNOWFLAKE_*` env vars (account, user, password, warehouse, database, schema)
or Streamlit secrets (`st.secrets`). The app must fall back to demo with a visible warning
if live credentials are absent or the connection fails. Snowflake SQL lives in `sql/`
(`01_schema.sql` … `04_audit.sql`); loading via `sql/02_load.py`.

## Skill execution order (fixed pipeline)

```
360-profiler → signal-reader → next-best-action-orchestrator
     (scores)       (signals)              (decision + draft + audit)
```

1. **360-profiler** (`.coco/skills/360-profiler/SKILL.md`) — nightly or ad-hoc; produces
   Attention (0–100) + Opportunity (0–100) per customer via `app/engine.py :: score_customer`.
2. **signal-reader** (`.coco/skills/signal-reader/SKILL.md`) — pre-action scan of
   `data/call_transcripts.md` + `data/support_emails.md`; produces signals list + CLEAR/HOLD clearance.
3. **next-best-action-orchestrator** (`.coco/skills/next-best-action-orchestrator/SKILL.md`) —
   evaluates decision branches in order, drafts the message, writes one append-only audit row.

The orchestrator must never run without fresh profiler scores AND a fresh signal scan.
If either is missing, stop and report which one — do not guess.

## Dual-mode rules

- **Demo is the default.** Sidebar toggle: Demo / Live. Demo reads `data/` + `data/audit_log.csv`.
- **Live reads credentials from env vars or `st.secrets` only.** If live is selected but
  credentials are missing/unreachable → fall back to demo and show a warning banner.
- The Streamlit app has 3 tabs: **Priority Feed** (ranked table, attention color-coded
  red ≥80 / amber 60–79 / yellow 30–59 / green <30, expandable trace), **Customer 360**
  (KPIs, accounts, transactions, repayments, signals, recommended action + draft),
  **Action Queue** (decisions, editable draft, Approve → audit write + mark done, audit log table).
- `app/engine.py` is importable standalone (no Streamlit import at module level).

## Fixed constants

- Anchor date "today" = **2026-10-06**. Never use the system clock for DPD/dormancy math.
- Randomness seed **42** wherever randomness is needed.
- Currency **INR (₹)** everywhere.

## Safety (non-negotiable)

- **Never invent credentials.** No hardcoded secrets, passwords, or tokens anywhere —
  code, docs, skills, or chat. Env vars / `st.secrets` only.
- **Never contact real customers.** All data in this repo is synthetic (fake names, fake
  `+91 98XXX XXXXX` phones, `examplemail.com` emails). Drafts are for demo/approval only;
  nothing is ever sent.
- **Audit every decision.** Each orchestrator decision writes exactly one append-only row
  (`data/audit_log.csv` in demo, `RELATEIQ_DEMO.OPS.ACTIONS_AUDIT` live). Never UPDATE or
  DELETE audit rows; a correction is a new row. An unaudited action must never reach a customer.
- **Dispute-open = DO NOT CONTACT.** Hard rule, no exceptions, no matter the scores.
- **No lorem ipsum.** Drafts use real fields from the customer record; if a field is unknown,
  mark it `[confirm ...]` for Arjun — never invent numbers.
- **Deterministic scoring.** The exact weights, bands, and branch thresholds live in the
  skill files; copy them verbatim — do not "improve" the model mid-run.

## Repo map

```
.coco/skills/360-profiler/SKILL.md
.coco/skills/signal-reader/SKILL.md
.coco/skills/next-best-action-orchestrator/SKILL.md
AGENTS.md                        ← this file
SPEC.md                          ← full build spec (source of truth)
app/engine.py                    ← score_customer + decide (standalone-importable)
app/main.py                      ← Streamlit app (3 tabs)
sql/01_schema.sql … 04_audit.sql ← Snowflake DDL + Cortex model
data/                            ← customers/accounts/transactions/repayments CSVs,
                                   call_transcripts.md, support_emails.md, audit_log.csv
docs/                            ← ARCHITECTURE.md, DEMO_SCRIPT.md, SUBMISSION_BRIEF.txt, deck_outline.md
demo/VIDEO_SCRIPT.md
README.md
```
