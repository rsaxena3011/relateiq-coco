#!/usr/bin/env python3
"""Independent verification of RelateIQ generated data (re-reads files)."""
import csv
import re
from datetime import date
from pathlib import Path

ANCHOR = date(2026, 10, 6)
W0, W1 = date(2026, 7, 8), date(2026, 10, 6)
D = Path(__file__).resolve().parent
fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def read_csv(name):
    with open(D / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


cust = read_csv("customers.csv")
acc = read_csv("accounts.csv")
txn = read_csv("transactions.csv")
rep = read_csv("repayments.csv")

# --- headers exact
check(list(cust[0].keys()) == ["customer_id", "name", "segment", "region",
      "tenure_months", "credit_score", "credit_limit", "utilization_pct",
      "missed_payments_12m", "avg_days_late", "products_held", "lifetime_value",
      "behavior_profile", "contact_email", "contact_phone"],
      "customers.csv columns exact")
check(list(acc[0].keys()) == ["account_id", "customer_id", "product_type",
      "sanctioned_limit", "outstanding", "status", "opened_date"],
      "accounts.csv columns exact")
check(list(txn[0].keys()) == ["txn_id", "account_id", "txn_date", "amount",
      "category", "channel"], "transactions.csv columns exact")
check(list(rep[0].keys()) == ["repayment_id", "account_id", "due_date",
      "paid_date", "amount_due", "amount_paid", "days_late"],
      "repayments.csv columns exact")

# --- row counts
check(len(cust) == 40, f"customers = 40 (got {len(cust)})")
check(60 <= len(acc) <= 80, f"accounts ~70 (got {len(acc)})")
check(700 <= len(txn) <= 900, f"transactions ~800 (got {len(txn)})")
check(330 <= len(rep) <= 470, f"repayments ~400 (got {len(rep)})")
check([c["customer_id"] for c in cust] == [f"CUST-{i:03d}" for i in range(1, 41)],
      "customer ids CUST-001..CUST-040")

# --- referential integrity
cids = {c["customer_id"] for c in cust}
aids = {a["account_id"] for a in acc}
check(all(a["customer_id"] in cids for a in acc), "accounts -> customers RI")
check(all(t["account_id"] in aids for t in txn), "transactions -> accounts RI")
check(all(r["account_id"] in aids for r in rep), "repayments -> accounts RI")
n_acc = {}
for a in acc:
    n_acc.setdefault(a["customer_id"], 0)
    n_acc[a["customer_id"]] += 1
check(all(1 <= v <= 3 for v in n_acc.values()),
      "1-3 accounts per customer")
check(all(c["customer_id"] in n_acc for c in cust), "every customer has accounts")

# --- repayments math
ok = True
for r in rep:
    due = date.fromisoformat(r["due_date"])
    paid = date.fromisoformat(r["paid_date"]) if r["paid_date"] else None
    exp = max(0, ((paid or ANCHOR) - due).days)
    if int(r["days_late"]) != exp:
        ok = False
    if (r["paid_date"] == "") != (r["amount_paid"] == "0"):
        ok = False
check(ok, "days_late = max(0,(paid|anchor)-due); paid empty <=> amount_paid 0")

# --- transaction window
check(all(W0 <= date.fromisoformat(t["txn_date"]) <= W1 for t in txn),
      "all txn dates within 2026-07-08..2026-10-06")
check(all(t["category"] in {"Shopping", "Travel", "Bills", "Cash Withdrawal",
                            "EMI Debit"} for t in txn), "txn categories valid")
check(all(t["channel"] in {"App", "POS", "Online"} for t in txn),
      "txn channels valid")

# --- missed/avg consistency vs repayment rows
late_by_cust = {}
acc2cust = {a["account_id"]: a["customer_id"] for a in acc}
for r in rep:
    if int(r["days_late"]) > 0:
        late_by_cust.setdefault(acc2cust[r["account_id"]], []).append(int(r["days_late"]))
ok = True
for c in cust:
    lates = late_by_cust.get(c["customer_id"], [])
    if int(c["missed_payments_12m"]) != min(8, len(lates)):
        ok = False; print("  missed mismatch", c["customer_id"])
    exp_avg = round(sum(lates) / len(lates) + 1e-9) if lates else 0
    # generator uses floor(mean+0.5); compare with tolerance-free exact recompute
    import math
    exp_avg = math.floor(sum(lates) / len(lates) + 0.5) if lates else 0
    if int(c["avg_days_late"]) != exp_avg:
        ok = False; print("  avg mismatch", c["customer_id"])
check(ok, "missed_payments_12m / avg_days_late match repayment rows")

# --- story anchors
by_name = {c["name"]: c for c in cust}
a = by_name["Rohan Khanna"]
check(a["behavior_profile"] == "high-value" and a["tenure_months"] == "60"
      and a["utilization_pct"] == "92" and a["missed_payments_12m"] == "3",
      "anchor Rohan Khanna profile")
a = by_name["Sneha Iyer"]
check(a["behavior_profile"] == "delinquent" and a["missed_payments_12m"] == "5",
      "anchor Sneha Iyer profile")
a = by_name["Amit Verma"]
check(a["missed_payments_12m"] == "0", "anchor Amit Verma clean record")
a = by_name["Kavya Nair"]
check(a["behavior_profile"] == "loyal" and a["utilization_pct"] == "15"
      and a["credit_score"] == "810" and a["tenure_months"] == "48",
      "anchor Kavya Nair profile")
a = by_name["Vikram Rao"]
check(a["behavior_profile"] == "dormant" and int(a["lifetime_value"]) >= 200000,
      "anchor Vikram Rao dormant + high LTV")
check(not any(t["account_id"] in {x["account_id"] for x in acc
              if x["customer_id"] == a["customer_id"]} for t in txn),
      "anchor Vikram Rao: zero transactions in 90-day window")
a = by_name["Divya Menon"]
check(a["behavior_profile"] == "new" and a["tenure_months"] == "4"
      and a["missed_payments_12m"] == "1", "anchor Divya Menon profile")
# current DPD spot checks
def dpd(cid):
    ds = [int(r["days_late"]) for r in rep
          if acc2cust[r["account_id"]] == cid and r["paid_date"] == ""]
    return max(ds) if ds else 0
check(dpd(by_name["Sneha Iyer"]["customer_id"]) > 30, "Sneha current DPD > 30")
check(dpd(by_name["Rohan Khanna"]["customer_id"]) == 0, "Rohan current DPD = 0")
d = dpd(by_name["Divya Menon"]["customer_id"])
check(1 <= d <= 30, f"Divya current DPD small (got {d})")

# --- signals in markdown
def sections(path):
    txt = (D / path).read_text(encoding="utf-8")
    parts = re.split(r"(?m)(?=^## CUST-)", txt)
    return [p for p in parts if p.startswith("## CUST-")]

def sig_counts(path):
    counts = {}
    for s in sections(path):
        m = re.search(r"\[SIGNAL: ([a-z-]+)\]", s)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts

tc = sig_counts("call_transcripts.md")
check(sum(tc.values()) == 10, f"10 transcripts with signals (got {sum(tc.values())})")
for sig in ["churn-risk", "dispute-open", "complaint", "life-event", "upsell-window"]:
    check(tc.get(sig, 0) >= 2, f"transcripts: {sig} x{tc.get(sig, 0)} (>=2)")
ec = sig_counts("support_emails.md")
check(sum(ec.values()) == 10, f"10 email threads with signals (got {sum(ec.values())})")
etxt = (D / "support_emails.md").read_text(encoding="utf-8")
check("Amit Verma" in etxt and "[SIGNAL: dispute-open]" in etxt,
      "emails include Amit Verma double-charge dispute")
check("Rohan Khanna" in etxt and "[SIGNAL: complaint]" in etxt,
      "emails include Rohan Khanna complaint")
# transcript line counts 8-15
ok = True
for s in sections("call_transcripts.md"):
    if "## CUST-" not in s:
        continue
    n = len(re.findall(r"^(Agent|Customer): ", s, re.M))
    if not (8 <= n <= 15):
        ok = False; print("  transcript line count off:", n)
check(ok, "each transcript has 8-15 dialogue lines")
# email thread lengths 2-4
ok = True
for s in sections("support_emails.md"):
    if "## CUST-" not in s:
        continue
    n = len(re.findall(r"^\*\*From:\*\*", s, re.M))
    if not (2 <= n <= 4):
        ok = False; print("  email msg count off:", n)
check(ok, "each email thread has 2-4 messages")

# --- field ranges / formats
check(all(c["behavior_profile"] in {"loyal", "at-risk", "delinquent", "new",
      "dormant", "high-value"} for c in cust), "behavior_profile vocab")
check(all(re.fullmatch(r"\+91 98\d{3} \d{5}", c["contact_phone"]) for c in cust),
      "phone format +91 98XXX XXXXX")
check(all(c["contact_email"].endswith("@examplemail.com") for c in cust),
      "email domain examplemail.com")
check(len({c["contact_email"] for c in cust}) == 40, "emails unique")
check(len({c["contact_phone"] for c in cust}) == 40, "phones unique")
check(all(a["status"] in {"Active", "Delinquent", "Closed"} for a in acc),
      "account status vocab")
check(all(a["product_type"] in {"Personal Loan", "Credit Card", "BNPL",
      "Two-wheeler Loan", "Gold Loan"} for a in acc), "product_type vocab")

print()
print("RESULT:", "ALL CHECKS PASSED" if not fails else f"{len(fails)} FAILURES")
raise SystemExit(1 if fails else 0)
