"""RelateIQ scoring + next-best-action engine (Snowflake CoCo CLI Hackathon, PS2).

Author: Ratnesh Saxena. Anchor date ("today"): 2026-10-06. Currency: INR (₹).

Importable standalone: from repo root, `from app.engine import score_customer`.
Only stdlib imports, so Streamlit demo mode needs no extra deps beyond
streamlit+pandas.

Scoring weights (deterministic, no randomness):

ATTENTION SCORE (max 100; higher = needs attention now):
    Delinquency DPD (max 35):   current max DPD 0 -> 0; 1-15 -> 12;
                                16-30 -> 20; 31-60 -> 28; 60+ -> 35
    Missed history (max 15):    missed_payments_12m 0 -> 0; 1 -> 5;
                                2-3 -> 10; 4+ -> 15
    Utilization stress (max 15): utilization_pct >= 90 -> 15; >= 70 -> 10;
                                >= 50 -> 6; else -> 2
    Credit deterioration (max 10): credit_score < 600 -> 10; < 650 -> 7;
                                < 700 -> 4; else -> 0
    Dormancy (max 10):          days since last txn > 90 -> 10; > 60 -> 6;
                                > 30 -> 3; else -> 0 (no txns at all -> 10)
    Unstructured signals (max 15): churn-risk -> 15; dispute-open -> 10;
                                complaint -> 8; life-event -> 5; else -> 0
                                (sum of signal points, capped at 15)

    Attention bands: 0-29 Healthy, 30-59 Watch, 60-79 High, 80-100 Critical.

OPPORTUNITY SCORE (max 100):
    credit_score >= 750 -> 30 (else >= 700 -> 15)
    utilization_pct < 30 -> 25 (else < 50 -> 12)
    missed_payments_12m == 0 -> 20
    tenure_months >= 24 -> 15
    upsell-window signal present -> 10
    (capped at 100)

NBA DECISION BRANCHES (evaluated in order):
    1. dispute-hold       if 'dispute-open' in signals -> no outreach,
                          internal flag for review.
    2. churn-intervention  if 'churn-risk' in signals and lifetime_value
                          >= 200000 -> human callback task brief.
    3. collections-firm   if dpd > 30 or missed_payments_12m >= 4.
    4. collections-gentle  if dpd >= 1.
    5. retention-offer     if attention >= 60 and dpd == 0, OR the
                          complaint-retention rule below.
    6. upsell              if opportunity >= 70 and attention < 30.
    Fallback: monitor (no action needed today).

    Retention widening (integration fix, data workstream 2026-10-06): branch 5
    also fires when 'complaint' is in signals and lifetime_value >= 200000 and
    dpd == 0. Why: an unresolved complaint on a high-LTV customer is a retention
    risk even when structured delinquency is low (e.g. Rohan Khanna scores only
    ~37 attention under the spec weights, so the pure attention>=60 gate can
    never fire for him, yet losing him costs real LTV). All other branches and
    thresholds are exactly as specced.
"""

from __future__ import annotations

import csv
import os
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

TODAY = date(2026, 10, 6)
SEED = 42  # anchor; the engine itself uses no randomness

# Repo layout: engine.py lives in <repo>/app/; data lives in <repo>/data/.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")

VALID_SIGNALS = (
    "churn-risk", "dispute-open", "complaint",
    "life-event", "upsell-window", "none",
)

# Per-signal attention points (sum capped at 15).
_SIGNAL_POINTS = {
    "churn-risk": 15,
    "dispute-open": 10,
    "complaint": 8,
    "life-event": 5,
    "upsell-window": 0,
    "none": 0,
}

# Priority order for display ("top signal").
_SIGNAL_PRIORITY = (
    "dispute-open", "churn-risk", "complaint", "life-event", "upsell-window",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_iso(iso: str) -> Optional[date]:
    try:
        y, m, d = (int(x) for x in str(iso).strip().split("-"))
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _fmt_inr(amount: float) -> str:
    """1234567 -> '₹12,34,567' (Indian digit grouping)."""
    n = int(round(amount))
    s = str(abs(n))
    if len(s) <= 3:
        grouped = s
    else:
        tail, head = s[-3:], s[:-3]
        parts = []
        while len(head) > 2:
            parts.append(head[-2:])
            head = head[:-2]
        parts.append(head)
        grouped = ",".join(reversed(parts)) + "," + tail
    return f"₹{'-' if n < 0 else ''}{grouped}"


def _fmt_date(iso: str) -> str:
    """'2026-09-21' -> '21 Sep 2026'."""
    d = _parse_iso(iso)
    return d.strftime("%d %b %Y") if d else (iso or "n/a")


def attention_band(score: int) -> str:
    """0-29 Healthy, 30-59 Watch, 60-79 High, 80-100 Critical."""
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 30:
        return "Watch"
    return "Healthy"


def current_dpd(repayments: List[Dict]) -> int:
    """Max days-late across UNPAID repayments.

    days_late per spec = max(0, (paid_date or 2026-10-06) - due_date).
    For unpaid rows this equals (TODAY - due_date).days floored at 0.
    """
    dpd = 0
    for r in repayments:
        paid = str(r.get("paid_date") or "").strip()
        if paid:
            continue  # settled rows do not drive current DPD
        due = _parse_iso(str(r.get("due_date") or ""))
        if not due:
            continue
        dpd = max(dpd, max(0, (TODAY - due).days))
    return dpd


def top_signal(signals: List[str]) -> str:
    """Highest-priority non-'none' signal, else 'none'."""
    for s in _SIGNAL_PRIORITY:
        if s in signals:
            return s
    return "none"


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _w_dpd(dpd: int) -> Tuple[int, str]:
    if dpd <= 0:
        pts, band = 0, "0"
    elif dpd <= 15:
        pts, band = 12, "1-15"
    elif dpd <= 30:
        pts, band = 20, "16-30"
    elif dpd <= 60:
        pts, band = 28, "31-60"
    else:
        pts, band = 35, "60+"
    return pts, f"Delinquency: current DPD {dpd} (band {band}) -> {pts}/35"


def _w_missed(missed: int) -> Tuple[int, str]:
    if missed <= 0:
        pts, band = 0, "0"
    elif missed == 1:
        pts, band = 5, "1"
    elif missed <= 3:
        pts, band = 10, "2-3"
    else:
        pts, band = 15, "4+"
    return pts, f"Missed history: {missed} missed payments in 12m (band {band}) -> {pts}/15"


def _w_utilization(util: int) -> Tuple[int, str]:
    if util >= 90:
        pts, band = 15, ">= 90"
    elif util >= 70:
        pts, band = 10, ">= 70"
    elif util >= 50:
        pts, band = 6, ">= 50"
    else:
        pts, band = 2, "< 50"
    return pts, f"Utilization stress: {util}% credit utilization (band {band}) -> {pts}/15"


def _w_credit(score: int) -> Tuple[int, str]:
    if score < 600:
        pts, band = 10, "< 600"
    elif score < 650:
        pts, band = 7, "< 650"
    elif score < 700:
        pts, band = 4, "< 700"
    else:
        pts, band = 0, ">= 700"
    return pts, f"Credit deterioration: score {score} (band {band}) -> {pts}/10"


def _w_dormancy(txns: List[Dict]) -> Tuple[int, str]:
    latest: Optional[date] = None
    for t in txns:
        d = _parse_iso(str(t.get("txn_date") or ""))
        if d and (latest is None or d > latest):
            latest = d
    if latest is None:
        # Empty transaction list = dormant 91+ days (not missing data).
        return 10, "Dormancy: no transactions in 90-day window (91+ days) -> 10/10"
    days = (TODAY - latest).days
    if days > 90:
        pts, band = 10, "> 90"
    elif days > 60:
        pts, band = 6, "> 60"
    elif days > 30:
        pts, band = 3, "> 30"
    else:
        pts, band = 0, "<= 30"
    return pts, (
        f"Dormancy: last transaction {days} days ago "
        f"({latest.isoformat()}, band {band}) -> {pts}/10"
    )


def _w_signals(signals: List[str]) -> Tuple[int, str]:
    parts, total = [], 0
    for s in signals:
        p = _SIGNAL_POINTS.get(s, 0)
        if p:
            parts.append(f"{s} (+{p})")
            total += p
    total = min(15, total)
    detail = ", ".join(parts) if parts else "no scoring signals"
    return total, f"Unstructured signals: {detail} -> {total}/15"


def _opp_breakdown(cust: Dict, signals: List[str]) -> Tuple[int, List[str]]:
    score, lines = _to_int(cust.get("credit_score")), []
    util = _to_int(cust.get("utilization_pct"))
    missed = _to_int(cust.get("missed_payments_12m"))
    tenure = _to_int(cust.get("tenure_months"))
    total = 0

    if score >= 750:
        pts = 30
    elif score >= 700:
        pts = 15
    else:
        pts = 0
    total += pts
    lines.append(f"Opportunity: credit score {score} -> {pts}/30")

    if util < 30:
        pts = 25
    elif util < 50:
        pts = 12
    else:
        pts = 0
    total += pts
    lines.append(f"Opportunity: utilization {util}% -> {pts}/25")

    pts = 20 if missed == 0 else 0
    total += pts
    lines.append(f"Opportunity: {missed} missed payments in 12m -> {pts}/20")

    pts = 15 if tenure >= 24 else 0
    total += pts
    lines.append(f"Opportunity: tenure {tenure} months -> {pts}/15")

    pts = 10 if "upsell-window" in signals else 0
    total += pts
    lines.append(f"Opportunity: upsell-window signal present -> {pts}/10")

    return min(100, total), lines


def score_customer(
    cust: Dict,
    accounts: List[Dict],
    repayments: List[Dict],
    txns: List[Dict],
    signals: List[str],
) -> Tuple[int, int, List[str]]:
    """Score one customer.

    Returns (attention 0-100, opportunity 0-100, trace). The trace is a list
    of human-readable lines, one per attention component, then the opportunity
    breakdown, then totals. Fully deterministic.
    """
    dpd = current_dpd(repayments)
    missed = _to_int(cust.get("missed_payments_12m"))
    util = _to_int(cust.get("utilization_pct"))
    credit = _to_int(cust.get("credit_score"))

    trace: List[str] = [f"Scoring {cust.get('customer_id')} {cust.get('name')} (as of {TODAY.isoformat()})"]
    attention = 0
    for pts, line in (
        _w_dpd(dpd),
        _w_missed(missed),
        _w_utilization(util),
        _w_credit(credit),
        _w_dormancy(txns),
        _w_signals(signals),
    ):
        attention += pts
        trace.append(line)
    attention = max(0, min(100, attention))

    opportunity, opp_lines = _opp_breakdown(cust, signals)
    trace.extend(opp_lines)
    trace.append(f"TOTAL: attention {attention}/100 ({attention_band(attention)}), "
                 f"opportunity {opportunity}/100")
    return attention, opportunity, trace

# ---------------------------------------------------------------------------
# Next-best-action decisions
# ---------------------------------------------------------------------------

def _outstanding_estimate(cust: Dict) -> float:
    """Estimated outstanding = credit_limit * utilization_pct / 100."""
    return _to_float(cust.get("credit_limit")) * _to_int(cust.get("utilization_pct")) / 100.0


def _topup_offer(cust: Dict) -> int:
    """Deterministic pre-approved top-up: 50% of unused limit, rounded to 5000."""
    headroom = _to_float(cust.get("credit_limit")) - _outstanding_estimate(cust)
    offer = int(headroom * 0.5 // 5000 * 5000)
    return max(25000, offer)


def decide(
    cust: Dict,
    attention: int,
    opportunity: int,
    signals: List[str],
    dpd: int,
) -> Tuple[str, str, str]:
    """Pick the next best action. Branches evaluated in order:

    1. dispute-hold        if 'dispute-open' in signals
    2. churn-intervention  if 'churn-risk' in signals and lifetime_value >= 200000
    3. collections-firm    if dpd > 30 or missed_payments_12m >= 4
    4. collections-gentle  if dpd >= 1
    5. retention-offer     if attention >= 60 and dpd == 0, OR
                          ('complaint' in signals and lifetime_value >= 200000
                          and dpd == 0). An unresolved complaint on a high-LTV
                          customer is a retention risk even when structured
                          delinquency is low (integration fix: the pure
                          attention>=60 gate could never fire for customers like
                          Rohan Khanna)
    6. upsell              if opportunity >= 70 and attention < 30
    Fallback: monitor.

    Returns (action, reason, draft). All drafts are from Arjun Mehta,
    Relationship Manager, with fields filled from the data.
    """
    name = str(cust.get("name") or "Customer").strip()
    first = name.split()[0]
    ltv = _to_int(cust.get("lifetime_value"))
    missed = _to_int(cust.get("missed_payments_12m"))
    tenure = _to_int(cust.get("tenure_months"))
    score = _to_int(cust.get("credit_score"))
    outstanding = _outstanding_estimate(cust)
    sig = top_signal(signals)

    # 1. Dispute hold: internal flag only, never a customer message.
    if "dispute-open" in signals:
        reason = ("Open dispute on file (signal: dispute-open). All outreach is "
                  "on hold until the dispute is resolved; contacting the customer "
                  "now risks the relationship and the case.")
        draft = (
            f"INTERNAL FLAG - DO NOT SEND TO CUSTOMER\n"
            f"Customer: {name} ({cust.get('customer_id')}) | "
            f"Attention {attention}, Opportunity {opportunity}\n"
            f"ACTION: dispute-hold. Reason: {reason}\n"
            f"Next step: Arjun to review the dispute thread (double-charge / "
            f"billing query), coordinate with the disputes desk, and clear this "
            f"flag only after a credit note or written resolution.\n"
            f"-- Arjun Mehta, Relationship Manager"
        )
        return "dispute-hold", reason, draft

    # 2. Churn intervention: human callback task brief.
    if "churn-risk" in signals and ltv >= 200000:
        reason = (f"Churn-risk signal with lifetime value {_fmt_inr(ltv)} "
                  f"(≥ ₹2,00,000). High-value at-risk customers need a human "
                  f"callback, not an automated message.")
        draft = (
            f"CALLBACK TASK BRIEF - for Arjun Mehta (internal)\n"
            f"Customer: {name} ({cust.get('customer_id')}), {tenure} months tenure, "
            f"LTV {_fmt_inr(ltv)}, credit score {score}.\n"
            f"Signal: churn-risk (top signal: {sig}). Attention {attention}/100.\n"
            f"Objective: save the relationship. Talking points: acknowledge the "
            f"recent experience, ask what changed, offer a concrete make-good "
            f"(fee waiver up to ₹2,500 or a 0.5% rate review on the active "
            f"loan), and agree a follow-up date on the call.\n"
            f"Do not pitch new products on this call.\n"
            f"-- Arjun Mehta, Relationship Manager"
        )
        return "churn-intervention", reason, draft

    # 3. Firm collections.
    if dpd > 30 or missed >= 4:
        trigger = f"DPD {dpd} (> 30)" if dpd > 30 else f"{missed} missed payments in 12m (>= 4)"
        reason = (f"Firm collections: {trigger}. Soft reminders have not worked; "
                  f"escalate tone, state consequences, demand a payment date.")
        draft = (
            f"Subject: Urgent: overdue amount of {_fmt_inr(outstanding)} "
            f"({dpd} days past due)\n\n"
            f"Dear {first},\n\n"
            f"This is Arjun Mehta, your Relationship Manager. I am writing about "
            f"your overdue balance of {_fmt_inr(outstanding)}, now {dpd} days past "
            f"due across your accounts with us.\n\n"
            f"I need a firm payment date from you within 48 hours. If the amount "
            f"is not cleared or a plan agreed by then, the account will be "
            f"flagged for recovery action and the delinquency will be reported to "
            f"the credit bureaus, which will affect your credit score.\n\n"
            f"If there is a genuine difficulty, call me directly and we will work "
            f"out a structured plan. But I do need to hear from you.\n\n"
            f"Regards,\nArjun Mehta\nRelationship Manager"
        )
        return "collections-firm", reason, draft

    # 4. Gentle collections.
    if dpd >= 1:
        reason = (f"Gentle collections: DPD {dpd}. Early-stage delinquency, a "
                  f"polite reminder with easy payment options is the right nudge.")
        draft = (
            f"Subject: Quick reminder: payment of {_fmt_inr(outstanding)} is "
            f"{dpd} days overdue\n\n"
            f"Dear {first},\n\n"
            f"I hope you are well. I am Arjun Mehta, your Relationship Manager. "
            f"A quick note that a payment of {_fmt_inr(outstanding)} on your "
            f"account is {dpd} days overdue.\n\n"
            f"If this slipped your mind, you can clear it in under a minute from "
            f"the app (Pay Now), or reply to this email and I will share a payment "
            f"link. If you have already paid, please ignore this note.\n\n"
            f"Warm regards,\nArjun Mehta\nRelationship Manager"
        )
        return "collections-gentle", reason, draft

    # 5. Retention offer.
    # Widened (integration fix, data workstream 2026-10-06): an unresolved
    # complaint on a high-LTV customer is a retention risk even when
    # structured delinquency is low, so complaint + high LTV + zero DPD also
    # qualifies. All other branches/thresholds exactly as specced.
    complaint_retention = "complaint" in signals and ltv >= 200000 and dpd == 0
    if (attention >= 60 and dpd == 0) or complaint_retention:
        if complaint_retention and not (attention >= 60 and dpd == 0):
            trigger = (f"unresolved complaint on a high-LTV customer "
                       f"({_fmt_inr(ltv)}) with zero DPD")
        else:
            trigger = f"attention {attention} (>= 60) with zero DPD"
        reason = (f"Retention offer: {trigger}. "
                  f"A proactive goodwill offer protects the relationship.")
        draft = (
            f"Subject: A small thank-you from us, {first}\n\n"
            f"Dear {first},\n\n"
            f"I am Arjun Mehta, your Relationship Manager. You have been with us "
            f"for {tenure} months, and I wanted to reach out personally.\n\n"
            f"As a gesture of appreciation, I have arranged for you: a full waiver "
            f"of your annual card fee (₹2,500) for this year, plus a 0.5% "
            f"reduction on the interest rate of your active personal loan for the "
            f"next 12 months. No forms, no calls needed; it is already applied.\n\n"
            f"If anything about your accounts is bothering you, reply to this "
            f"email and I will sort it out myself.\n\n"
            f"Warm regards,\nArjun Mehta\nRelationship Manager"
        )
        return "retention-offer", reason, draft

    # 6. Upsell.
    if opportunity >= 70 and attention < 30:
        offer = _topup_offer(cust)
        reason = (f"Upsell: opportunity {opportunity} (>= 70) with attention "
                  f"{attention} (< 30). Strong profile, low risk; pre-approved "
                  f"top-up is the next best action.")
        draft = (
            f"Subject: {first}, you are pre-approved for a top-up of {_fmt_inr(offer)}\n\n"
            f"Dear {first},\n\n"
            f"Good news from my side. Based on your excellent repayment record "
            f"over the last {tenure} months (credit score {score}), you are "
            f"pre-approved for a top-up of {_fmt_inr(offer)} on your existing "
            f"facility, at your current interest rate.\n\n"
            f"No fresh paperwork, no waiting: accept from the app and the amount "
            f"is disbursed to your account the same day. The offer is valid for "
            f"14 days.\n\n"
            f"Happy to walk you through the numbers on a quick call if you like.\n\n"
            f"Warm regards,\nArjun Mehta\nRelationship Manager"
        )
        return "upsell", reason, draft

    # Fallback: monitor.
    reason = (f"Monitor: attention {attention}, opportunity {opportunity}, no "
              f"branch matched. No outreach needed today; keep on routine watch.")
    draft = (
        f"INTERNAL NOTE - no customer outreach today\n"
        f"Customer: {name} ({cust.get('customer_id')}) | Attention {attention} "
        f"({attention_band(attention)}), Opportunity {opportunity}, DPD {dpd}, "
        f"top signal: {sig}.\n"
        f"ACTION: monitor. Next review in the next daily run.\n"
        f"-- Arjun Mehta, Relationship Manager"
    )
    return "monitor", reason, draft


# ---------------------------------------------------------------------------
# Data loading (Demo mode: data/*.csv + data/call_transcripts.md + support_emails.md)
# ---------------------------------------------------------------------------

def _read_csv(path: str) -> List[Dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _index(rows: List[Dict], key: str) -> Dict[str, List[Dict]]:
    idx: Dict[str, List[Dict]] = {}
    for r in rows:
        idx.setdefault(str(r.get(key) or ""), []).append(r)
    return idx


def parse_signal_markdown(path: str, name_to_id: Dict[str, str]) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """Parse a transcripts/emails .md file into signals and raw text per customer.

    Sections are split on `## ` headers. A section is attributed to the first
    CUST-XXX id found in its header/body, else by matching a customer name.
    Every `[SIGNAL: <signal>]` tag in the section is recorded (deduped, in
    priority order). Returns (signals_by_customer, text_by_customer).
    """
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return {}, {}
    signals: Dict[str, List[str]] = {}
    texts: Dict[str, str] = {}
    for chunk in re.split(r"(?m)^##\s+", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        found = [s for s in re.findall(r"\[SIGNAL:\s*([a-z-]+)\]", chunk)
                 if s in VALID_SIGNALS and s != "none"]
        match = re.search(r"(CUST-\d{3})", chunk)
        cid = match.group(1) if match else None
        if not cid:
            lowered = chunk.lower()
            for cname, c_id in name_to_id.items():
                if cname.lower() in lowered:
                    cid = c_id
                    break
        if not cid:
            continue
        ordered = [s for s in _SIGNAL_PRIORITY if s in found]
        prev = signals.get(cid, [])
        signals[cid] = prev + [s for s in ordered if s not in prev]
        texts[cid] = texts.get(cid, "") + "\n\n---\n\n" + chunk if cid in texts else chunk
    return signals, texts


def _merge_signals(*maps: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {}
    for m in maps:
        for cid, sigs in m.items():
            prev = merged.get(cid, [])
            merged[cid] = prev + [s for s in sigs if s not in prev]
    return merged


def load_demo_data(data_dir: Optional[str] = None) -> Dict:
    """Load data/customers.csv, accounts.csv, transactions.csv, repayments.csv,
    call_transcripts.md, support_emails.md.

    Returns dict with: customers, customers_by_id, accounts_by_customer,
    txns_by_account, repayments_by_account, signals_by_customer,
    transcripts, emails.
    """
    data_dir = data_dir or _DATA_DIR
    customers = _read_csv(os.path.join(data_dir, "customers.csv"))
    accounts = _read_csv(os.path.join(data_dir, "accounts.csv"))
    transactions = _read_csv(os.path.join(data_dir, "transactions.csv"))
    repayments = _read_csv(os.path.join(data_dir, "repayments.csv"))

    customers_by_id = {str(c.get("customer_id")): c for c in customers}
    name_to_id = {str(c.get("name")): str(c.get("customer_id")) for c in customers}
    accounts_by_customer = _index(accounts, "customer_id")
    txns_by_account = _index(transactions, "account_id")
    repayments_by_account = _index(repayments, "account_id")

    t_signals, transcripts = parse_signal_markdown(
        os.path.join(data_dir, "call_transcripts.md"), name_to_id)
    e_signals, emails = parse_signal_markdown(
        os.path.join(data_dir, "support_emails.md"), name_to_id)
    signals_by_customer = _merge_signals(t_signals, e_signals)

    return {
        "customers": customers,
        "customers_by_id": customers_by_id,
        "accounts": accounts,
        "accounts_by_customer": accounts_by_customer,
        "transactions": transactions,
        "txns_by_account": txns_by_account,
        "repayments": repayments,
        "repayments_by_account": repayments_by_account,
        "signals_by_customer": signals_by_customer,
        "transcripts": transcripts,
        "emails": emails,
    }


def _rows_for_customer(data: Dict, cust: Dict) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Collect (accounts, repayments, txns) for one customer."""
    cid = str(cust.get("customer_id"))
    accounts = data["accounts_by_customer"].get(cid, [])
    repayments, txns = [], []
    for a in accounts:
        aid = str(a.get("account_id"))
        repayments.extend(data["repayments_by_account"].get(aid, []))
        txns.extend(data["txns_by_account"].get(aid, []))
    return accounts, repayments, txns


def run_pipeline(data: Optional[Dict] = None) -> List[Dict]:
    """Score every customer and decide the next best action.

    Returns customers ranked by attention (desc), then opportunity (desc),
    then customer_id. Each item: customer_id, name, segment, attention, band,
    opportunity, dpd, signals, top_signal, action, reason, draft, trace.
    Deterministic.
    """
    data = data or load_demo_data()
    results = []
    for cust in data["customers"]:
        cid = str(cust.get("customer_id"))
        accounts, repayments, txns = _rows_for_customer(data, cust)
        signals = data["signals_by_customer"].get(cid, [])
        dpd = current_dpd(repayments)
        attention, opportunity, trace = score_customer(
            cust, accounts, repayments, txns, signals)
        action, reason, draft = decide(cust, attention, opportunity, signals, dpd)
        results.append({
            "customer_id": cid,
            "name": cust.get("name"),
            "segment": cust.get("segment"),
            "attention": attention,
            "band": attention_band(attention),
            "opportunity": opportunity,
            "dpd": dpd,
            "signals": signals,
            "top_signal": top_signal(signals),
            "action": action,
            "reason": reason,
            "draft": draft,
            "trace": trace,
            "cust": cust,
            "accounts": accounts,
            "repayments": repayments,
            "txns": txns,
        })
    results.sort(key=lambda r: (-r["attention"], -r["opportunity"], r["customer_id"]))
    return results


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def append_audit(data_dir: Optional[str], record: Dict) -> str:
    """Append one decision record to data/audit_log.csv (created on first write).

    Record keys: timestamp, customer_id, action, attention, opportunity, reason.
    Returns the path written.
    """
    data_dir = data_dir or _DATA_DIR
    path = os.path.join(data_dir, "audit_log.csv")
    fields = ["timestamp", "customer_id", "action", "attention", "opportunity", "reason"]
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: record.get(k, "") for k in fields})
    return path


# ---------------------------------------------------------------------------
# Tiny inline fixtures (for engine validation before data/ CSVs land)
# ---------------------------------------------------------------------------

def demo_fixtures() -> Dict:
    """2-3 tiny fixture customers in the exact SPEC schema shape, to validate
    scoring/decision logic before the real data/ CSVs are built."""
    customers = [
        {"customer_id": "CUST-101", "name": "Amit Verma", "segment": "Self-Employed",
         "region": "Mumbai", "tenure_months": "30", "credit_score": "700",
         "credit_limit": "400000", "utilization_pct": "45", "missed_payments_12m": "1",
         "avg_days_late": "5", "products_held": "2", "lifetime_value": "150000",
         "behavior_profile": "at-risk", "contact_email": "amit.verma1@examplemail.com",
         "contact_phone": "+91 98111 11111"},
        {"customer_id": "CUST-102", "name": "Kavya Nair", "segment": "Salaried",
         "region": "Bengaluru", "tenure_months": "48", "credit_score": "810",
         "credit_limit": "800000", "utilization_pct": "15", "missed_payments_12m": "0",
         "avg_days_late": "0", "products_held": "3", "lifetime_value": "320000",
         "behavior_profile": "loyal", "contact_email": "kavya.nair2@examplemail.com",
         "contact_phone": "+91 98222 22222"},
        {"customer_id": "CUST-103", "name": "Sneha Iyer", "segment": "Salaried",
         "region": "Chennai", "tenure_months": "20", "credit_score": "615",
         "credit_limit": "300000", "utilization_pct": "88", "missed_payments_12m": "5",
         "avg_days_late": "38", "products_held": "2", "lifetime_value": "90000",
         "behavior_profile": "delinquent", "contact_email": "sneha.iyer3@examplemail.com",
         "contact_phone": "+91 98333 33333"},
    ]
    accounts = [
        {"account_id": "ACC-901", "customer_id": "CUST-101", "product_type": "Personal Loan",
         "sanctioned_limit": "400000", "outstanding": "180000", "status": "Active",
         "opened_date": "2024-04-01"},
        {"account_id": "ACC-902", "customer_id": "CUST-101", "product_type": "Credit Card",
         "sanctioned_limit": "100000", "outstanding": "45000", "status": "Active",
         "opened_date": "2025-01-15"},
        {"account_id": "ACC-903", "customer_id": "CUST-102", "product_type": "Personal Loan",
         "sanctioned_limit": "800000", "outstanding": "120000", "status": "Active",
         "opened_date": "2022-10-01"},
        {"account_id": "ACC-904", "customer_id": "CUST-103", "product_type": "Personal Loan",
         "sanctioned_limit": "300000", "outstanding": "264000", "status": "Delinquent",
         "opened_date": "2025-02-01"},
        {"account_id": "ACC-905", "customer_id": "CUST-103", "product_type": "Credit Card",
         "sanctioned_limit": "150000", "outstanding": "99000", "status": "Active",
         "opened_date": "2025-06-01"},
    ]
    repayments = [
        {"repayment_id": "R-1", "account_id": "ACC-901", "due_date": "2026-10-01",
         "paid_date": "", "amount_due": "15200", "amount_paid": "0", "days_late": "5"},
        {"repayment_id": "R-2", "account_id": "ACC-903", "due_date": "2026-10-01",
         "paid_date": "2026-09-30", "amount_due": "22400", "amount_paid": "22400", "days_late": "0"},
        {"repayment_id": "R-3", "account_id": "ACC-904", "due_date": "2026-08-22",
         "paid_date": "", "amount_due": "18900", "amount_paid": "0", "days_late": "45"},
        {"repayment_id": "R-4", "account_id": "ACC-904", "due_date": "2026-09-06",
         "paid_date": "", "amount_due": "18900", "amount_paid": "0", "days_late": "30"},
    ]
    transactions = [
        {"txn_id": "T-1", "account_id": "ACC-902", "txn_date": "2026-10-02",
         "amount": "4500", "category": "Shopping", "channel": "Online"},
        {"txn_id": "T-2", "account_id": "ACC-903", "txn_date": "2026-10-05",
         "amount": "8200", "category": "Bills", "channel": "App"},
        {"txn_id": "T-3", "account_id": "ACC-904", "txn_date": "2026-08-01",
         "amount": "12000", "category": "Cash Withdrawal", "channel": "POS"},
    ]
    customers_by_id = {c["customer_id"]: c for c in customers}
    return {
        "customers": customers,
        "customers_by_id": customers_by_id,
        "accounts": accounts,
        "accounts_by_customer": _index(accounts, "customer_id"),
        "transactions": transactions,
        "txns_by_account": _index(transactions, "account_id"),
        "repayments": repayments,
        "repayments_by_account": _index(repayments, "account_id"),
        "signals_by_customer": {
            "CUST-101": ["dispute-open"],
            "CUST-102": ["upsell-window"],
            "CUST-103": ["complaint"],
        },
        "transcripts": {
            "CUST-101": "Agent: ... Customer reports a double charge on the card.\n[SIGNAL: dispute-open]",
        },
        "emails": {},
    }


if __name__ == "__main__":
    # Fixture validation run (works even before data/ CSVs exist).
    results = run_pipeline(demo_fixtures())
    print(f"Scored {len(results)} customers (fixtures)")
    for r in results:
        print(f"{r['customer_id']} {r['name']:<12} att={r['attention']:>3} "
              f"opp={r['opportunity']:>3} dpd={r['dpd']:>2} -> {r['action']}")
