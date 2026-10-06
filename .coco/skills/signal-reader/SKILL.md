# Skill: signal-reader

Pre-action signal scan of unstructured data (call transcripts + support email threads).
**Must run BEFORE `next-best-action-orchestrator` evaluates any customer.** No outreach
decision is valid without a fresh signal scan.

## Trigger

- Immediately before the orchestrator evaluates a customer (single or batch).
- Re-run for a customer the moment a new transcript or email thread lands for them.

## Inputs

| # | Input | Demo path | Live (Snowflake) |
|---|-------|-----------|------------------|
| 1 | `customer_id` | — | — |
| 2 | Call transcripts | `data/call_transcripts.md` | `RELATEIQ_DEMO.OPS.CALL_TRANSCRIPTS` (`customer_id`, `transcript_md`) |
| 3 | Support emails | `data/support_emails.md` | `RELATEIQ_DEMO.OPS.SUPPORT_EMAILS` (`customer_id`, `thread_md`) |

## Steps

1. Look up `customer_id` in both sources. Read the **full** transcript/thread, not just the
   `[SIGNAL: ...]` tag — the tag is ground truth, the text is context for the brief.
2. Collect every signal found. Multiple signals per customer are allowed; report all of them.
3. **Clearance decision:**
   - `dispute-open` ∈ signals → clearance = **HOLD — DO NOT CONTACT**.
   - otherwise → clearance = **CLEAR**.
4. Write the signal brief (see Outputs).

## Signal vocabulary (exact — no synonyms, no paraphrase)

- `churn-risk` — customer signals intent to leave/close (dormancy + competitor mention, closure request).
- `dispute-open` — unresolved billing/charge dispute. **HARD RULE: dispute-open → DO NOT CONTACT
  the customer.** The orchestrator writes no outreach draft for them; it routes to `dispute-hold`
  (internal review flag only) until the dispute is closed.
- `complaint` — service/product complaint with no open billing dispute.
- `life-event` — job change, relocation, marriage, medical event; context for tone, may shift the action.
- `upsell-window` — customer asks about limits, top-ups, or new products.
- `none` — no signal found in any source. A valid, reportable result.

## Outputs

**Signal brief** per customer:
- `customer_id`
- sources checked (transcript: y/n, email: y/n)
- signals list (exact vocabulary)
- clearance: `CLEAR` or `HOLD`
- 2–3 line summary with dates and amounts (e.g. "Double EMI debit ₹18,450 × 2 on 27–28 Sep 2026;
  refund initiated 29 Sep, not credited as of 2026-10-06.")

The orchestrator consumes: signals list + clearance flag. The 360-profiler consumes the signals
list for the unstructured-signals component of the Attention Score.

## Error handling

- **No transcript/email on file** → signals=`[none]`, clearance `CLEAR`,
  note `"no unstructured data on file"`.
- **Tag missing or malformed** → read the text and assign the closest exact vocabulary term;
  note `"[SIGNAL:] tag missing — inferred from text, verify"`.
- **Conflicting signals** (e.g. `complaint` + `upsell-window`) → report both; the orchestrator's
  ordered branches resolve the conflict. `dispute-open` always wins for clearance.
- **Never invent a signal to fill a gap.** `none` is always an acceptable answer.

## Worked example — Amit Verma, double-charge → dispute-hold

`data/support_emails.md`, thread dated 2026-09-28:

> Customer: "I was charged my EMI twice this month — ₹18,450 debited on 27 Sep AND 28 Sep.
> Reverse one immediately."
> Agent: "Confirmed duplicate debit on your loan account. Refund initiated, will credit in 3–5 working days."
> `[SIGNAL: dispute-open]`

`data/call_transcripts.md`: no entry for Amit Verma.

**Output:**
- customer_id: `<Amit Verma's id from data/customers.csv>`
- sources: transcript n, email y
- signals: `[dispute-open]`
- clearance: **HOLD**
- brief: "Double EMI debit (₹18,450 × 2, 27–28 Sep 2026); refund initiated 29 Sep, not yet
  credited as of 2026-10-06. DO NOT CONTACT until dispute closed."
