# Skill: next-best-action-orchestrator

Takes a scored customer + their signal brief and produces exactly one next best action,
a ready-to-use draft, and an append-only audit record. **Branches are evaluated in order;
the first matching branch wins.**

## Trigger

After `360-profiler` (scores) and `signal-reader` (signals + clearance) have both run for
the customer. Never run on scores alone.

## Inputs

- `cust` (customer record), `attention` (int), `opportunity` (int), `signals` (list),
  `dpd` (current max days-past-due, int), `clearance` (`CLEAR`/`HOLD`).

## Branch logic — evaluate in this exact order

`decide(cust, attention, opportunity, signals, dpd) -> (action, reason, draft)`

1. **`dispute-hold`** — if `dispute-open` ∈ signals.
   No customer outreach. Internal review flag only.
2. **`churn-intervention`** — if `churn-risk` ∈ signals AND `lifetime_value` ≥ 200000.
   Human callback task brief for Arjun Mehta (not an auto-sent message).
3. **`collections-firm`** — if `dpd` > 30 OR `missed_payments_12m` ≥ 4.
   Firm nudge message.
4. **`collections-gentle`** — if `dpd` ≥ 1.
   Gentle reminder.
5. **`retention-offer`** — if `attention` ≥ 60 AND `dpd` == 0.
   Personalized offer (fee waiver / rate reduction).
6. **`upsell`** — if `opportunity` ≥ 70 AND `attention` < 30.
   Pre-approved top-up offer.

If no branch matches → action `monitor`, reason `"healthy — no action required"`, draft empty.

## Drafting tone guidelines (all drafts signed by Arjun Mehta, Relationship Manager)

- **`dispute-hold`:** no customer-facing message, ever. Draft = internal flag:
  `"INTERNAL FLAG — DO NOT CONTACT <name>. Open dispute: <one-line summary>. Review within 24h."`
- **`churn-intervention`:** callback task brief, warm and senior. Include: why they're at risk
  (signal quote), LTV at stake, suggested talking points, best contact window. This is a brief
  for a human call — not a message to send.
- **`collections-firm`:** firm but respectful. State the DPD, the overdue amount, a clear payment
  deadline, and the consequence of continued default. No threats beyond stated policy, no blame language.
- **`collections-gentle`:** friendly reminder that assumes oversight. One clear CTA
  (pay in the app / reply to this message). Short.
- **`retention-offer`:** appreciative and personal. Name the customer's history (tenure, products),
  name the concrete offer (e.g. "2% rate reduction for 12 months" or "annual fee waived"),
  one acceptance step. No hard sell.
- **`upsell`:** congratulatory on their track record. Pre-approved top-up amount, key terms
  (rate, tenure), explicit opt-in CTA. Never imply the top-up is already disbursed.
- **Universal:** realistic, fields filled from the customer record. No lorem ipsum, no `[insert name]`
  placeholders. Currency INR (₹).

## Audit-write procedure (append-only — NEVER update or delete)

Every decision writes exactly one audit row, once, at decision time.

**Demo** — append to `data/audit_log.csv` (create with header if missing):

```
decided_at,customer_id,action,attention_score,opportunity_score,reason,message,decided_by
```

- `decided_at`: ISO-8601 with IST offset (e.g. `2026-10-06T09:00:00+05:30`).
- `message`: the full draft (or internal flag for `dispute-hold`).
- `decided_by`: `relateiq-agent` (or the approving human's name after manual approval in the Action Queue).

**Live** — `INSERT` into `RELATEIQ_DEMO.OPS.ACTIONS_AUDIT`:

```sql
INSERT INTO RELATEIQ_DEMO.OPS.ACTIONS_AUDIT
  (customer_id, action, attention_score, opportunity_score, reason, message)
VALUES
  (:customer_id, :action, :attention, :opportunity, :reason, :message);
-- decided_at defaults to CURRENT_TIMESTAMP(); decided_by defaults to 'relateiq-agent'
```

Rules:
- Append-only: `INSERT` / file-append only. **Never `UPDATE`, never `DELETE`.** A corrected
  decision is a NEW row; the old row stays as history.
- One decision → one row. If the orchestrator re-runs for the same customer, that is a second row.
- Write the audit row even when the action is `dispute-hold` or `monitor` — "decided to do nothing"
  is a decision compliance must see.
- Quote CSV fields containing commas/newlines per RFC 4180.

## Outputs

Per customer: `(action, reason, draft)` + the written audit row id/line.
Batch: the Action Queue — decisions with action badge, editable draft, Approve → audit write + mark done;
audit log table rendered at the bottom (Streamlit Tab 3).

## Error handling

- **Scores missing** → do not decide; return error `"scores missing — run 360-profiler first"`.
- **Signals missing** → do not decide; return error `"signals missing — run signal-reader first"`.
  Exception: never default a missing signal to `dispute-open` or `none` — require the scan.
- **Audit write fails** → the decision is NOT complete. Retry once; if it still fails, surface the
  decision as `"unlogged"` and block outreach until the write succeeds. An unaudited action
  must never reach a customer.
- **Draft references data not in the record** (amounts, dates) → leave the specific field as a
  bracketed TODO for Arjun, e.g. `[confirm overdue amount]` — never invent numbers.

## Worked end-to-end example — Amit Verma → dispute-hold

**1. 360-profiler output.** Inputs: `credit_score` 690, `utilization_pct` 55,
`missed_payments_12m` 1, DPD 0, last txn 3 days ago, `tenure_months` 20, signals `[dispute-open]`.
Attention = 0 (DPD 0) + 5 (missed 1) + 6 (util ≥50) + 4 (credit <700) + 0 (dormancy) + 10
(`dispute-open`) = **25 → Healthy**. Opportunity = **0** (no component fires).

**2. signal-reader output.** signals=`[dispute-open]`, clearance=**HOLD**.
Brief: "Double EMI debit (₹18,450 × 2, 27–28 Sep 2026); refund initiated 29 Sep, not yet
credited as of 2026-10-06. DO NOT CONTACT until dispute closed."

**3. decide.** Branch 1: `dispute-open` ∈ signals → **`dispute-hold`**.
Reason: `"[SIGNAL: dispute-open] in support_emails.md (double EMI debit ₹18,450, 27–28 Sep 2026); refund pending. No outreach until dispute closed."`
Draft (internal flag only):
`"INTERNAL FLAG — DO NOT CONTACT Amit Verma. Open dispute: duplicate EMI debit of ₹18,450 (27–28 Sep 2026), refund initiated 29 Sep not yet credited. Review within 24h. — Arjun Mehta"`

**4. Audit write** (`data/audit_log.csv`):

```
2026-10-06T09:00:00+05:30,CUST-007,dispute-hold,25,0,"[SIGNAL: dispute-open] in support_emails.md (double EMI debit ₹18,450, 27–28 Sep 2026); refund pending. No outreach until dispute closed.","INTERNAL FLAG — DO NOT CONTACT Amit Verma. Open dispute: duplicate EMI debit of ₹18,450 (27–28 Sep 2026), refund initiated 29 Sep not yet credited. Review within 24h. — Arjun Mehta",relateiq-agent
```

(`CUST-007` is illustrative — use Amit Verma's actual id from `data/customers.csv`.)
