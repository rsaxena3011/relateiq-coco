# RelateIQ - Demo Video Script (3–5 minutes)

**Format:** screen recording with voiceover. Target runtime: ~4:00. All data is synthetic (40 demo customers); anchor date 2026-10-06. No em dashes in any on-screen text. Recommended capture: 1920×1080, cursor highlighted.

---

## PART 1 - INPUT: THE DATA AND THE PERSONA (0:00–1:00)

### Shot 1 (0:00–0:20) - The problem

**On-screen action:** Title card: "RelateIQ" with the line "Customer 360 + Next Best Action Engine (PS2)". Cut to a simple text slide: "2,000 borrowers. 1 relationship manager. Every morning."

**Narration:**
> Meet Arjun Mehta, a relationship manager at a digital lender. Every morning he faces two thousand borrowers and one question: who needs attention today, and exactly what should I do about each one? Today, he guesses. RelateIQ ends the guessing.

### Shot 2 (0:20–0:40) - The structured data

**On-screen action:** File explorer or editor showing `data/customers.csv`, `data/accounts.csv`, `data/transactions.csv`, `data/repayments.csv`. Scroll briefly through the customers table headers. Show one row: Rohan Khanna's.

**Narration:**
> The engine fuses structured data first. Forty customers, seventy accounts, eight hundred transactions, four hundred repayment records. Tenure, credit utilization, missed payments, days past due: the full ledger.

### Shot 3 (0:40–1:00) - The unstructured data

**On-screen action:** Open `data/call_transcripts.md` and `data/support_emails.md` side by side. Scroll to Amit Verma's double-charge email thread; highlight the `[SIGNAL: dispute-open]` tag. Then show a churn-risk transcript tag.

**Narration:**
> Then the unstructured side: call transcripts and support emails, tagged with intent signals. Amit Verma was double-charged. That signal will change everything about what happens next.

---

## PART 2 - PROCESSING: THE THREE SKILLS AT WORK (1:00–2:50)

### Shot 4 (1:00–1:20) - Skill 1: 360 Profiler

**On-screen action:** Open `.cortex/skills/360-profiler/SKILL.md` briefly, then switch to the app, Priority Feed tab. The ranked table renders: Sneha Iyer at the top (red), Kavya Nair at the bottom (green).

**Narration:**
> Skill one is the 360 Profiler. It fuses accounts, transactions, and repayment history into two numbers per customer: an Attention Score from zero to a hundred, and an Opportunity Score. Forty customers ranked in seconds, red critical down to green healthy.

### Shot 5 (1:20–1:40) - Score transparency

**On-screen action:** Expand Sneha Iyer's row. Slowly scroll the reasoning trace: delinquency, missed history, utilization, signals. Point at the band label (High/Critical).

**Narration:**
> Nothing is a black box. Expand any row and the profiler shows its work: every score component with its banded weight, and the signal that tipped it. Sneha Iyer: five missed payments, high days past due. The math is on the screen.

### Shot 6 (1:40–2:05) - Skill 2: Signal Reader

**On-screen action:** Open `.cortex/skills/signal-reader/SKILL.md` briefly. Switch to Customer 360 tab, select Amit Verma. Show his signal chips: `dispute-open`. Show the recommended action badge: `dispute-hold`.

**Narration:**
> Skill two is the Signal Reader. It scans every transcript and email for intent: churn risk, disputes, complaints, life events, upsell windows. Amit's double-charge became a dispute-open signal, and the engine did the only safe thing: dispute-hold. No outreach. Internal review. One dunning message to a disputed customer can end the relationship; this skill stops it.

### Shot 7 (2:05–2:50) - Skill 3: Next-Best-Action Orchestrator

**On-screen action:** Open `.cortex/skills/next-best-action-orchestrator/SKILL.md` briefly, then show the Action Queue tab. Scroll through the six decision branches in action: Amit Verma → dispute-hold; Vikram Rao → churn-intervention (human callback brief); Sneha Iyer → collections-firm; Divya Menon → collections-gentle; Rohan Khanna → retention-offer; Kavya Nair → upsell (pre-approved top-up). Open one draft message (Kavya's upsell or Sneha's firm nudge) to show the filled fields.

**Narration:**
> Skill three is the orchestrator. It evaluates six decision branches in a fixed order: dispute-hold, churn intervention, collections firm, collections gentle, retention offer, upsell. Vikram Rao, dormant ninety days with high lifetime value, gets a human callback brief. Kavya Nair, loyalty and a spotless record, gets a pre-approved top-up with the amount filled in. Each branch drafts the outreach in Arjun's voice, ready to review.

---

## PART 3 - OUTPUT: ACTIONS, DRAFTS, AUDIT (2:50–3:50)

### Shot 8 (2:50–3:15) - Approve in the Action Queue

**On-screen action:** In the Action Queue, edit one draft slightly in the text area (show the human-in-the-loop), then click Approve. The row updates to "done".

**Narration:**
> The human stays in the loop. Every draft is editable; Arjun approves, and only then does the decision become final. The agent drafts; the manager decides.

### Shot 9 (3:15–3:35) - The audit trail

**On-screen action:** Scroll to the audit log table at the bottom of the Action Queue. Point at the columns: timestamp, customer_id, action, attention, opportunity, reason. Optionally open `data/audit_log.csv` to show the append-only file.

**Narration:**
> And every approved action lands in an append-only audit table: timestamp, customer, action, both scores, and the reason. Compliance gets a complete trail for free, with zero extra work from the team.

### Shot 10 (3:35–3:50) - Dual mode and close

**On-screen action:** Flip the sidebar Demo/Live toggle; show the fallback warning gracefully continuing in Demo mode; flip back. Final title card: "RelateIQ · Arjun no longer guesses."

**Narration:**
> Demo mode runs on synthetic data with two pip installs. Flip one toggle and the same scoring contract runs live on Snowflake with a Cortex Analyst semantic model. RelateIQ turns a morning of guesswork into a ranked queue in seconds: zero dispute-duns, a full audit trail, and projected wins on delinquency and upsell. Arjun no longer guesses. He just opens the feed.

---

## Production notes

- Re-record any shot where the score band or action for an anchor customer does not match the SPEC anchors (Amit: dispute-hold; Vikram: churn-intervention; Sneha: collections-firm; Divya: collections-gentle; Rohan: retention-offer; Kavya: upsell).
- All contact emails and phone numbers in the data are synthetic; a "synthetic data" caption is recommended on Shots 2–3.
- Narration pace: ~140 words per minute; total script ≈ 560 words ≈ 4:00.
