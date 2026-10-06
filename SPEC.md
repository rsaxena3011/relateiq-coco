# RelateIQ — Build Spec (Snowflake CoCo CLI Hackathon 2026, GCC Edition)

**Author:** Ratnesh Saxena (Solo). Deadline 2026-10-06 23:59 IST.
**Problem Statement:** PS2 — Customer 360 and Next Best Action Engine.
**What:** RelateIQ, a Customer 360 + Next Best Action Engine for a digital lender (NBFC).

## The story
Arjun Mehta, Relationship Manager at a digital lender with 2,000 retail borrowers. Every morning he needs to know: which customers need attention TODAY and exactly what to do about each one. Today he guesses. RelateIQ fuses structured account data with unstructured conversation signals and tells him the next best action per customer, with reasoning he can trust and an audit trail for compliance.

## The agent — 3 modular CoCo skills
1. **360 Profiler** — fuses structured data: accounts, transactions, repayment history, credit utilization, tenure → Attention Score (0–100, higher = needs attention now) + Opportunity Score (0–100).
2. **Signal Reader** — unstructured: call transcripts + support email threads + KYC notes → intent signals: `churn-risk`, `dispute-open`, `complaint`, `life-event`, `upsell-window`, `none`.
3. **Next-Best-Action Orchestrator** — decision branches per customer (in order): (a) dispute-hold, (b) churn-intervention (human callback), (c) collections-firm, (d) collections-gentle, (e) retention-offer, (f) upsell (pre-approved top-up). Drafts the outreach message, writes every decision to an append-only audit table.

## Anchor date
"Today" = 2026-10-06. Deterministic: seed 42 for any randomness. Currency: INR (₹).

## Data schemas (EXACT)

### data/customers.csv (40 rows)
`customer_id,name,segment,region,tenure_months,credit_score,credit_limit,utilization_pct,missed_payments_12m,avg_days_late,products_held,lifetime_value,behavior_profile,contact_email,contact_phone`
- customer_id: CUST-001 … CUST-040
- segment: Salaried, Self-Employed, Small Business
- region: Mumbai, Delhi NCR, Bengaluru, Chennai, Pune, Hyderabad
- tenure_months: 3–84 (int); credit_score: 580–820 (int)
- credit_limit: 50000–2000000 (int, INR); utilization_pct: 5–98 (int)
- missed_payments_12m: 0–8 (int); avg_days_late: 0–45 (int)
- products_held: 1–4 (int); lifetime_value: 10000–500000 (int)
- behavior_profile: `loyal`, `at-risk`, `delinquent`, `new`, `dormant`, `high-value`
- contact_email: firstname.lastnameN@examplemail.com style; contact_phone: +91 98XXX XXXXX (fake, clearly synthetic)
- Story anchors (must exist):
  - Rohan Khanna — high-value, tenure 60m, utilization 92%, missed 3 recently, recent complaint → retention-offer.
  - Sneha Iyer — delinquent, missed 5, high DPD → collections-firm.
  - Amit Verma — double-charged, dispute-open → dispute-hold.
  - Kavya Nair — loyal, utilization 15%, score 810, tenure 48m → upsell top-up.
  - Vikram Rao — dormant 90+ days, high LTV → churn-intervention callback.
  - Divya Menon — new, 4 months, first missed payment → collections-gentle.

### data/accounts.csv (~70 rows)
`account_id,customer_id,product_type,sanctioned_limit,outstanding,status,opened_date`
- account_id: ACC-001 …; product_type: Personal Loan, Credit Card, BNPL, Two-wheeler Loan, Gold Loan
- status: Active, Delinquent, Closed; 1–3 accounts per customer; opened_date within tenure.

### data/transactions.csv (~800 rows)
`txn_id,account_id,txn_date,amount,category,channel`
- Last 90 days only (2026-07-08 … 2026-10-06); category: Shopping, Travel, Bills, Cash Withdrawal, EMI Debit; channel: App, POS, Online.

### data/repayments.csv (~400 rows)
`repayment_id,account_id,due_date,paid_date,amount_due,amount_paid,days_late`
- paid_date empty when unpaid; days_late = max(0, (paid_date or 2026-10-06) − due_date).

### data/call_transcripts.md
~10 customers, short agent↔customer transcripts (8–15 lines each), Sep–Oct 2026 dates. End each with `[SIGNAL: <signal>]`. Cover: churn-risk (2), dispute-open (2), complaint (2), life-event (2), upsell-window (2).

### data/support_emails.md
~10 customers (overlap allowed), email threads 2–4 messages, Sep 2026. End each with `[SIGNAL: <signal>]`. Must include Amit Verma's double-charge dispute and Rohan Khanna's complaint.

Signals vocabulary (exact): `churn-risk`, `dispute-open`, `complaint`, `life-event`, `upsell-window`, `none`.

## Scoring engine (app/engine.py)
`score_customer(cust, accounts, repayments, txns, signals) -> (attention:int, opportunity:int, trace:list[str])`.

**Attention Score (max 100):**
- Delinquency DPD (max 35): current max DPD 0→0; 1–15→12; 16–30→20; 31–60→28; 60+→35.
- Missed history (max 15): 0→0; 1→5; 2–3→10; 4+→15.
- Utilization stress (max 15): ≥90→15; ≥70→10; ≥50→6; else 2.
- Credit deterioration (max 10): <600→10; <650→7; <700→4; else 0.
- Dormancy (max 10): days since last txn >90→10; >60→6; >30→3; else 0.
- Unstructured signals (max 15): churn-risk→15; dispute-open→10; complaint→8; life-event→5; else 0.
Bands: 0–29 Healthy, 30–59 Watch, 60–79 High, 80–100 Critical.

**Opportunity Score (max 100):** credit_score ≥750→30 (≥700→15); utilization <30→25 (<50→12); missed==0→20; tenure ≥24→15; upsell-window signal→10. Cap 100.

## NBA decision branches — evaluate in order
`decide(cust, attention, opportunity, signals, dpd) -> (action, reason, draft)`:
1. `dispute-hold` if `dispute-open` in signals → no outreach; internal flag for review.
2. `churn-intervention` if `churn-risk` in signals and lifetime_value ≥ 200000 → human callback task brief.
3. `collections-firm` if dpd > 30 or missed_payments_12m ≥ 4 → firm nudge message.
4. `collections-gentle` if dpd ≥ 1 → gentle reminder.
5. `retention-offer` if attention ≥ 60 and dpd == 0 → personalized offer (fee waiver / rate reduction).
6. `upsell` if opportunity ≥ 70 and attention < 30 → pre-approved top-up offer.
Drafts from Arjun Mehta (Relationship Manager), realistic, fields filled. No lorem ipsum.

## Audit
Every decision → timestamp, customer_id, action, attention, opportunity, reason. Demo: `data/audit_log.csv`. Live: Snowflake ACTIONS_AUDIT. Shown in Action Queue tab.

## Streamlit app (app/main.py + app/engine.py)
- Deps ONLY: streamlit, pandas. `streamlit run app/main.py`.
- Sidebar: "RelateIQ" header, "Arjun Mehta · Relationship Manager", Demo/Live toggle (default Demo; Live reads SNOWFLAKE_* env/st.secrets, falls back with warning).
- Tab 1 "Priority Feed": ranked customer table (customer, segment, attention score color-coded red≥80/amber 60–79/yellow 30–59/green<30, next-best-action badge, top signal), expandable reasoning trace per customer.
- Tab 2 "Customer 360": customer selectbox → KPIs (tenure, credit score, utilization, DPD, LTV, products), accounts table, recent transactions, repayment history, transcript + email signals, recommended action + draft.
- Tab 3 "Action Queue": decisions with action badge, editable draft (text_area), Approve → audit write + mark done; audit log table at bottom.
- engine.py importable standalone. Deployable: no API keys in demo.

## Snowflake SQL (sql/)
- 01_schema.sql: DATABASE RELATEIQ_DEMO, SCHEMA OPS, tables CUSTOMERS, ACCOUNTS, TRANSACTIONS, REPAYMENTS, CALL_TRANSCRIPTS (customer_id, transcript_md), SUPPORT_EMAILS (customer_id, thread_md), ACTIONS_AUDIT. Idempotent, types mirror CSVs.
- 02_load.py: snowflake-connector-python, env-only creds, loads data/ files.
- 03_cortex_analyst_model.yaml: semantic model `relateiq_model`, per-table dims/measures, 4–5 verified_queries ("customers needing attention today", "top upsell candidates", "open disputes", "delinquency by segment").
- 04_audit.sql: ACTIONS_AUDIT DDL (action_id autoincrement, decided_at default current_timestamp, customer_id, action, attention_score, opportunity_score, reason, message, decided_by default 'relateiq-agent') + append-only grant comments + sample INSERT.

## CoCo skills (.cortex/skills/*/)
- 360-profiler/SKILL.md — nightly profiling run: trigger, inputs, scoring model (copy weights), SQL/tools, outputs, errors, worked example.
- signal-reader/SKILL.md — pre-action signal scan: transcripts + emails, signal vocabulary, DO NOT CONTACT on dispute-open, worked example (Amit Verma).
- next-best-action-orchestrator/SKILL.md — branch logic with exact thresholds, drafting tone per branch, audit procedure, worked end-to-end example.
- Root AGENTS.md — CoCo CLI operating instructions: setup, skill order (360-profiler → signal-reader → next-best-action-orchestrator), dual-mode, safety (no invented creds, no real customers, audit everything).

## Docs & submission artifacts
- docs/ARCHITECTURE.md: text diagram, data flow, dual-mode, component map.
- docs/DEMO_SCRIPT.md: 90-second narrated demo (pain → run → branch → impact).
- demo/VIDEO_SCRIPT.md: 3–5 min demo video shot-by-shot (Input→Processing→Output, show all 3 skills).
- docs/SUBMISSION_BRIEF.txt: prototype brief ≤1024 chars (written by coordinator).
- docs/deck_outline.md: exact content for all 6 slides (Slide 1: Team Name "Ratnesh Saxena (Solo)", Problem Statement PS2, Team Leader Ratnesh Saxena, Team Size 1; Slide 2 Problem Brief; Slide 3 Architecture Diagram description; Slide 4 CoCo CLI skills + connections; Slide 5 Impact with numbers; Slide 6 roadmap).
- README.md: PS2-first pitch, setup both modes, repo map, rubric mapping table (40/30/30).

## Constraints
- No invented credentials/hardcoded secrets. Env vars only. Seed 42. Author Ratnesh Saxena. Clean commented code. Everything must run.
