# RelateIQ - Customer 360 + Next Best Action Engine

**Snowflake CoCo CLI Hackathon 2026 (GCC Edition) · Problem Statement PS2 · Author: Ratnesh Saxena (Solo)**

## The pain

Arjun Mehta is a Relationship Manager at a digital lender with 2,000 retail borrowers. Every morning he must answer: which customers need attention TODAY, and exactly what to do about each one. Today he guesses. Disputes get dunned, churners slip away, upsell windows close before anyone notices. Structured account data and unstructured conversation signals live in separate worlds, so no one sees the full customer.

## The turn

RelateIQ fuses both worlds into one decision per customer. Three modular CoCo skills run in sequence: the **360 Profiler** fuses accounts, transactions, repayment history, utilization, and tenure into an Attention Score (0-100) and an Opportunity Score (0-100), each with a human-readable reasoning trace; the **Signal Reader** extracts intent (`churn-risk`, `dispute-open`, `complaint`, `life-event`, `upsell-window`) from call transcripts and support emails; the **Next-Best-Action Orchestrator** picks one of six actions (dispute-hold, churn-intervention, collections-firm, collections-gentle, retention-offer, upsell), drafts the outreach in Arjun's voice, and writes every decision to an append-only audit table.

## The demo

A Streamlit app with three tabs: **Priority Feed** (40 customers ranked red-critical to green-healthy, expandable trace per row), **Customer 360** (KPIs, accounts, transactions, repayments, signals, recommended action + draft), **Action Queue** (editable drafts, Approve → audit write). Anchor customers: Amit Verma lands on dispute-hold (double-charge, zero outreach), Vikram Rao gets a human callback (dormant 90+ days, high LTV), Sneha Iyer gets a firm collections nudge, Divya Menon a gentle one, Rohan Khanna a retention offer, Kavya Nair a pre-approved top-up.

## Projected impact

- **Speed:** a full portfolio profiled, signal-scanned, and action-queued in seconds.
- **Risk:** zero dunning of customers with open disputes.
- **Revenue:** churn callbacks target high-LTV at-risk customers; upsell offers surface exactly when they qualify.
- **Trust:** every score shows its trace, every decision its reason, every action its audit row.
- **Projected outcomes:** delinquency (DSO) down through earlier, correctly-toned collections; upsell conversion up through perfectly timed offers.

## Setup

### Demo mode (default, zero infrastructure)

```bash
pip install streamlit pandas
streamlit run app/main.py
```

Synthetic data in `data/` (anchor date 2026-10-06, seed 42, currency INR). No API keys, no credentials, fully deterministic.

### Live mode (Snowflake + Cortex Analyst)

```bash
# 1. Create schema and tables
#    Run sql/01_schema.sql in your Snowflake account (creates RELATEIQ_DEMO.OPS)

# 2. Load the data
export SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... SNOWFLAKE_PASSWORD=...
export SNOWFLAKE_WAREHOUSE=... SNOWFLAKE_ROLE=...
python sql/02_load.py

# 3. In the app sidebar, flip the Demo/Live toggle.
#    Any connection failure falls back to Demo mode with a warning.
```

The Cortex Analyst semantic model (`sql/03_cortex_analyst_model.yaml`) defines `relateiq_model` with verified queries: "customers needing attention today", "top upsell candidates", "open disputes", "delinquency by segment". Audit writes go to `ACTIONS_AUDIT` (see `sql/04_audit.sql`).

## Repo map

```
relateiq/
├── SPEC.md                      # Build contract
├── README.md                    # This file
├── AGENTS.md                    # CoCo CLI operating instructions
├── app/
│   ├── main.py                  # Streamlit UI (Priority Feed / Customer 360 / Action Queue)
│   └── engine.py                # score_customer(), decide() - shared by Demo and Live
├── sql/
│   ├── 01_schema.sql            # RELATEIQ_DEMO.OPS DDL (idempotent)
│   ├── 02_load.py               # CSV/MD → Snowflake loader (env creds only)
│   ├── 03_cortex_analyst_model.yaml  # relateiq_model semantic model + verified queries
│   └── 04_audit.sql             # ACTIONS_AUDIT DDL (append-only) + sample INSERT
├── .coco/skills/
│   ├── 360-profiler/SKILL.md
│   ├── signal-reader/SKILL.md
│   └── next-best-action-orchestrator/SKILL.md
├── data/                        # Demo-mode source of truth (synthetic)
│   ├── customers.csv            # 40 customers
│   ├── accounts.csv             # ~70 accounts
│   ├── transactions.csv         # ~800 transactions (last 90 days)
│   ├── repayments.csv           # ~400 repayments
│   ├── call_transcripts.md      # ~10 transcripts with [SIGNAL: ...] tags
│   ├── support_emails.md        # ~10 email threads with [SIGNAL: ...] tags
│   └── audit_log.csv            # Created on first approved action
├── demo/
│   └── VIDEO_SCRIPT.md          # 3-5 min demo video, shot-by-shot
└── docs/
    ├── ARCHITECTURE.md          # System diagram, data flow, dual-mode, component map
    ├── DEMO_SCRIPT.md           # 90-second narrated demo with click-by-click cues
    ├── SUBMISSION_BRIEF.txt     # Prototype brief (≤1024 chars)
    └── deck_outline.md          # Exact content for all 6 slides
```

## Rubric mapping

| Criterion | Weight | How RelateIQ delivers |
|---|---|---|
| Technical Execution | 40% | Three modular, documented CoCo skills in `.coco/skills/`; a deterministic rules engine (`app/engine.py`) with weighted, explainable scoring and fixed-order decision branches; dual-mode data layer (local CSVs / Snowflake) behind one scoring contract; graceful Live-mode fallback; append-only audit in both modes; idempotent SQL and a Cortex Analyst semantic model with verified queries. |
| Real-World Relevance | 30% | Built for a real RM workflow at a digital lender: the daily "who needs attention today and what exactly to do" question. Anchor cases mirror real portfolio events (double-charge disputes, dormant high-LTV churners, delinquency ladders, pre-approved top-ups). The dispute-hold branch directly prevents revenue-destroying dunning; every draft stays human-approved. |
| Solution Completeness | 30% | End-to-end prototype: synthetic data → scoring → signal extraction → decision branches → drafted outreach → human approval → audit trail → Snowflake deployment path. Streamlit UI covers rank, diagnose, and act. Docs cover architecture, a 90-second demo script, a 3-5 minute video script, and a 6-slide deck outline. Everything runs from two pip installs. |

## Notes

- All data is synthetic; contact emails and phone numbers are clearly fake.
- No credentials are hardcoded anywhere; Live mode uses `SNOWFLAKE_*` env vars only.
- Deterministic: anchor date 2026-10-06, seed 42.
