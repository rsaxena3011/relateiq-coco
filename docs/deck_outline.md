# RelateIQ - Deck Outline (6 slides)

Exact content per slide. Visual guidance in brackets is for the presenter, not the slide.

---

## Slide 1 - Title

**Heading:** RelateIQ

**Subheading:** Customer 360 + Next Best Action Engine

**Body:**
- Team Name: Ratnesh Saxena (Solo)
- Problem Statement: PS2 (Customer 360 and Next Best Action Engine)
- Team Leader: Ratnesh Saxena
- Team Size: 1

[Visual: clean title layout, product name prominent.]

---

## Slide 2 - Problem Brief

**Heading:** The Problem: Arjun Guesses Every Morning

**Body:**
- Arjun Mehta, Relationship Manager at a digital lender, oversees 2,000 retail borrowers.
- Every morning he must answer: which customers need attention TODAY, and exactly what to do about each one.
- Today he guesses. The cost: disputes get dunned (relationships torched), churners slip away unnoticed, upsell windows close before anyone acts.
- The gap: structured account data and unstructured conversation signals (calls, emails) live in separate worlds, so no one sees the full customer picture.

**Key stat callout:** 2,000 borrowers · 1 manager · 0 single view of the customer.

[Visual: a split image or two panels: scattered spreadsheets and inboxes on the left, a single question mark on the right.]

---

## Slide 3 - Architecture Diagram

**Heading:** How It Works

**Body:** (narrate against the diagram; keep slide text minimal)

- Two modes, one engine. Demo: local CSVs + rules engine. Live: Snowflake + Cortex Analyst. Sidebar toggle with graceful fallback.
- Three modular CoCo skills in sequence: 360 Profiler (structured fusion into Attention + Opportunity scores) → Signal Reader (call transcripts + emails into intent signals) → Next-Best-Action Orchestrator (six decision branches, drafted outreach, append-only audit).
- One UI with three tabs: Priority Feed (rank), Customer 360 (diagnose), Action Queue (approve).

[Visual: the monospace system diagram from docs/ARCHITECTURE.md, cleaned up for the slide: data sources (left) → rules engine (center) → 3 skills → Streamlit UI → audit log (bottom).]

---

## Slide 4 - CoCo CLI Skills Used + How They Connect

**Heading:** Three Modular Skills, One Pipeline

**Body:**

| # | Skill | Input | Output |
|---|-------|-------|--------|
| 1 | 360-profiler | accounts, transactions, repayments, credit, tenure | Attention Score (0-100) + Opportunity Score (0-100) + reasoning trace |
| 2 | signal-reader | call_transcripts.md, support_emails.md | intent signal: churn-risk, dispute-open, complaint, life-event, upsell-window, none |
| 3 | next-best-action-orchestrator | scores + signals + DPD | action (1 of 6 branches) + reason + drafted outreach + audit write |

**Connection:** profiler output feeds the orchestrator's branch thresholds; signal-reader output gates the branches (dispute-open forces dispute-hold with zero outreach). Every decision appends to the audit table.

**Skill contracts live in:** `.coco/skills/360-profiler/SKILL.md`, `.coco/skills/signal-reader/SKILL.md`, `.coco/skills/next-best-action-orchestrator/SKILL.md`.

[Visual: three connected boxes with arrows: 1 → 2 → 3, plus a side arrow from 3 down to an "Audit" cylinder.]

---

## Slide 5 - Impact Statement

**Heading:** The Impact: From Guesswork to a Ranked Queue in Seconds

**Body:**
- Speed: a 40-customer portfolio is profiled, signal-scanned, and action-queued in seconds; the same engine scales to Arjun's full 2,000-borrower book.
- Risk eliminated: dispute-hold guarantees zero dunning of customers with open disputes (the Amit Verma case).
- Revenue protected and grown: churn-intervention callbacks target high-LTV at-risk customers (the Vikram Rao case); pre-approved top-up offers surface exactly when utilization and score qualify (the Kavya Nair case).
- Trust by design: every score shows its reasoning trace; every decision carries its reason; every approved action lands in an append-only audit table for compliance.
- Projected outcomes: delinquency (DSO) down through earlier, correctly-toned collections; upsell conversion up through perfectly timed offers.

[Visual: three mini case cards: Amit (dispute-hold, no contact), Vikram (callback), Kavya (pre-approved top-up), plus a small audit-log screenshot.]

---

## Slide 6 - Roadmap / Next Steps

**Heading:** What Comes Next

**Body:**
1. Live Snowflake wiring: run `sql/01_schema.sql` and `sql/02_load.py`, flip the toggle, validate parity between Demo and Live scores.
2. Cortex Analyst in production: ship the `relateiq_model` semantic model so analysts can ask "customers needing attention today" in plain language.
3. Real signal ingestion: replace the markdown fixtures with a nightly pipeline from the call-recording and ticketing systems.
4. Pilot with one RM team: measure dispute-dun rate, callback conversion, and upsell uptake against a control group for one quarter.
5. Expand the branch library: add branch variants (e.g., EMI restructuring, referral offers) as new data becomes available.

**Closing line:** Arjun no longer guesses. He just opens the feed.

[Visual: a 5-step timeline, ending with the product tagline.]
