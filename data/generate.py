#!/usr/bin/env python3
"""
RelateIQ - synthetic data generator (Snowflake CoCo CLI Hackathon, PS2).

Deterministic: every random draw comes from random.Random(42), in a fixed
order, so reruns are byte-identical. Anchor date ("today"): 2026-10-06.
Currency: INR.

Outputs (written next to this file, i.e. data/):
    customers.csv, accounts.csv, transactions.csv, repayments.csv,
    call_transcripts.md, support_emails.md
"""
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
ANCHOR = date(2026, 10, 6)        # "today" for the whole build
WINDOW_START = date(2026, 7, 8)   # 90-day transaction window start (inclusive)
OUT = Path(__file__).resolve().parent

rng = random.Random(SEED)


# ---------------------------------------------------------------- helpers
def rint(a, b):
    return rng.randint(a, b)


def pick(seq):
    return seq[rng.randrange(len(seq))]


def wpick(weighted):
    """weighted: list of (value, weight)."""
    total = sum(w for _, w in weighted)
    x = rng.random() * total
    for v, w in weighted:
        x -= w
        if x <= 0:
            return v
    return weighted[-1][0]


def iso(d):
    return d.isoformat()


# ---------------------------------------------------------------- customers
SEGMENTS = ["Salaried", "Self-Employed", "Small Business"]
REGIONS = ["Mumbai", "Delhi NCR", "Bengaluru", "Chennai", "Pune", "Hyderabad"]
PROFILES = ["loyal", "at-risk", "delinquent", "new", "dormant", "high-value"]

# Ranges for generated (non-anchor) customers: tenure, score, util, limit, ltv.
PROFILE_PARAMS = {
    "loyal":      dict(tenure=(12, 84), score=(700, 810), util=(8, 45),
                       limit=(100000, 1000000), ltv=(50000, 400000)),
    "at-risk":    dict(tenure=(12, 72), score=(620, 700), util=(55, 92),
                       limit=(100000, 800000), ltv=(30000, 250000)),
    "delinquent": dict(tenure=(12, 60), score=(580, 645), util=(70, 98),
                       limit=(50000, 400000), ltv=(15000, 150000)),
    "new":        dict(tenure=(3, 12), score=(650, 745), util=(20, 60),
                       limit=(50000, 400000), ltv=(10000, 80000)),
    "dormant":    dict(tenure=(36, 84), score=(700, 790), util=(5, 30),
                       limit=(300000, 1500000), ltv=(80000, 300000)),
    "high-value": dict(tenure=(36, 84), score=(720, 800), util=(50, 92),
                       limit=(800000, 2000000), ltv=(250000, 500000)),
}

# The 6 story anchors: exact profiles from the spec.
# late_plan entries: (account_position, due_position_recent_first, days_late | "unpaid")
ANCHORS = [
    dict(name="Rohan Khanna", segment="Salaried", region="Mumbai",
         tenure=60, score=688, limit=1500000, util=92, ltv=450000,
         profile="high-value", n_acc=2,
         late_plan=[(0, 1, 12), (1, 3, 20), (1, 5, 9)]),
    dict(name="Sneha Iyer", segment="Salaried", region="Chennai",
         tenure=24, score=592, limit=300000, util=88, ltv=95000,
         profile="delinquent", n_acc=2,
         late_plan=[(0, 0, "unpaid"), (0, 1, "unpaid"), (0, 2, "unpaid"),
                    (1, 1, "unpaid"), (1, 2, "unpaid")]),
    dict(name="Amit Verma", segment="Self-Employed", region="Delhi NCR",
         tenure=30, score=742, limit=800000, util=41, ltv=210000,
         profile="loyal", n_acc=2, late_plan=[]),
    dict(name="Kavya Nair", segment="Salaried", region="Bengaluru",
         tenure=48, score=810, limit=1000000, util=15, ltv=320000,
         profile="loyal", n_acc=2, late_plan=[]),
    dict(name="Vikram Rao", segment="Self-Employed", region="Hyderabad",
         tenure=72, score=765, limit=1200000, util=18, ltv=385000,
         profile="dormant", n_acc=2, late_plan=[]),
    dict(name="Divya Menon", segment="Salaried", region="Pune",
         tenure=4, score=682, limit=250000, util=55, ltv=28000,
         profile="new", n_acc=1, late_plan=[(0, 0, "unpaid")]),
]

# Named signal customers: each carries the signal used in transcripts + emails.
SIGNAL_CUSTOMERS = [
    dict(name="Aditya Kulkarni", segment="Salaried", region="Mumbai",
         tenure=30, score=668, limit=600000, util=78, ltv=240000,
         profile="at-risk", n_acc=2, signal="churn-risk",
         late_plan=[(0, 0, 9), (1, 2, 18)]),
    dict(name="Pooja Deshmukh", segment="Self-Employed", region="Delhi NCR",
         tenure=26, score=755, limit=500000, util=34, ltv=180000,
         profile="loyal", n_acc=2, signal="dispute-open", late_plan=[]),
    dict(name="Karan Malhotra", segment="Salaried", region="Bengaluru",
         tenure=22, score=640, limit=450000, util=85, ltv=130000,
         profile="at-risk", n_acc=2, signal="complaint",
         late_plan=[(0, 1, 22), (1, 3, 11)]),
    dict(name="Ananya Reddy", segment="Salaried", region="Chennai",
         tenure=10, score=690, limit=350000, util=48, ltv=60000,
         profile="new", n_acc=1, signal="life-event",
         late_plan=[(0, 0, "unpaid")]),
    dict(name="Suresh Pillai", segment="Small Business", region="Hyderabad",
         tenure=60, score=790, limit=900000, util=22, ltv=410000,
         profile="loyal", n_acc=2, signal="upsell-window", late_plan=[]),
]

ANCHOR_SIGNALS = {  # story anchors that carry an unstructured signal
    "Rohan Khanna": "complaint",
    "Amit Verma": "dispute-open",
    "Vikram Rao": "churn-risk",
    "Kavya Nair": "upsell-window",
    "Sneha Iyer": "life-event",
}

FIRST_M = ["Aarav", "Dev", "Ishaan", "Kunal", "Nikhil", "Rahul", "Rohit",
           "Varun", "Yash", "Kabir", "Manav", "Pranav", "Rajat", "Sahil", "Vivaan"]
FIRST_F = ["Diya", "Ishita", "Meera", "Neha", "Priya", "Riya", "Shreya",
           "Tanvi", "Aisha", "Zoya"]
LAST = ["Agarwal", "Bhatt", "Chopra", "Gupta", "Joshi", "Mishra", "Patel",
        "Sharma", "Shukla", "Singh", "Yadav", "Bose", "Chawla", "Dutta",
        "Khan", "Nambiar", "Oberoi", "Pandey", "Rathore", "Shetty"]


def make_contact(name, used_emails, used_phones):
    first, last = name.split(" ", 1)
    base = f"{first}.{last}@examplemail.com".lower()
    email = base
    n = 2
    while email in used_emails:
        email = base.replace("@", f"{n}@")
        n += 1
    used_emails.add(email)
    while True:
        phone = f"+91 98{rint(100, 999)} {rint(10000, 99999)}"
        if phone not in used_phones:
            used_phones.add(phone)
            break
    return email, phone


def _unique_name(used_names):
    """Name pool holds 500 unique combos; beyond that, numbered variants.

    Keeps the original pop-from-shuffled-pool draw order for the first 500
    so the default 40-customer run stays byte-identical.
    """
    base = [f"{f} {l}" for f in FIRST_M + FIRST_F for l in LAST
            if f"{f} {l}" not in used_names]
    if base:
        return base[rng.randrange(len(base))]
    name = f"{pick(FIRST_M + FIRST_F)} {pick(LAST)}"
    k = 2
    # NOTE: at this point every base combo is taken (base was empty), so only
    # the numbered variant needs checking. Do NOT add `name in used_names`
    # to the condition: it is always True here and would loop forever.
    while f"{name} {k}" in used_names:
        k += 1
    return f"{name} {k}"


def _gen_profile_counts(n_generated):
    """Profile mix scaled from the 29-customer reference mix."""
    weights = [("loyal", 10), ("at-risk", 6), ("delinquent", 4),
               ("new", 5), ("dormant", 2), ("high-value", 2)]
    total_w = sum(w for _, w in weights)
    counts, remaining = [], n_generated
    for j, (p, w) in enumerate(weights):
        if j == len(weights) - 1:
            k = remaining
        else:
            k = n_generated * w // total_w
            remaining -= k
        counts.extend([p] * k)
    assert len(counts) == n_generated
    return counts


def build_customers(n_generated=29):
    customers = []
    used_names, used_emails, used_phones = set(), set(), set()

    def add(cid, name, segment, region, tenure, score, limit, util, ltv,
            profile, n_acc, late_plan, signal=None):
        assert name not in used_names
        used_names.add(name)
        email, phone = make_contact(name, used_emails, used_phones)
        customers.append(dict(
            customer_id=cid, name=name, segment=segment, region=region,
            tenure_months=tenure, credit_score=score, credit_limit=limit,
            utilization_pct=util, lifetime_value=ltv, behavior_profile=profile,
            n_acc=n_acc, late_plan=late_plan, signal=signal,
            contact_email=email, contact_phone=phone))

    # 1-6: story anchors.
    for i, a in enumerate(ANCHORS, start=1):
        add(f"CUST-{i:03d}", a["name"], a["segment"], a["region"], a["tenure"],
            a["score"], a["limit"], a["util"], a["ltv"], a["profile"],
            a["n_acc"], a["late_plan"], ANCHOR_SIGNALS.get(a["name"]))

    # 7-11: named signal customers.
    for i, s in enumerate(SIGNAL_CUSTOMERS, start=7):
        add(f"CUST-{i:03d}", s["name"], s["segment"], s["region"], s["tenure"],
            s["score"], s["limit"], s["util"], s["ltv"], s["profile"],
            s["n_acc"], s["late_plan"], s["signal"])

    # 12+: generated customers.
    gen_profiles = _gen_profile_counts(n_generated)
    rng.shuffle(gen_profiles)
    name_pool = []
    for f in FIRST_M + FIRST_F:
        for l in LAST:
            if f"{f} {l}" not in used_names:
                name_pool.append(f"{f} {l}")
    rng.shuffle(name_pool)
    for i, profile in enumerate(gen_profiles, start=12):
        p = PROFILE_PARAMS[profile]
        name = name_pool.pop() if name_pool else _unique_name(used_names)
        tenure = rint(*p["tenure"])
        add(f"CUST-{i:03d}", name,
            wpick([("Salaried", 55), ("Self-Employed", 25), ("Small Business", 20)]),
            pick(REGIONS), tenure, rint(*p["score"]), rint(*p["limit"]) // 1000 * 1000,
            rint(*p["util"]), rint(*p["ltv"]) // 1000 * 1000, profile,
            1 + (rng.random() < 0.55) + (rng.random() < 0.18),
            late_plan="auto")
    assert len(customers) == 11 + n_generated
    return customers


# ---------------------------------------------------------------- accounts
PRODUCTS = ["Personal Loan", "Credit Card", "BNPL", "Two-wheeler Loan", "Gold Loan"]


def build_accounts(customers):
    accounts = []
    seq = 1
    for c in customers:
        n = c["n_acc"]
        chosen = []
        for j in range(n):
            pool = [p for p in PRODUCTS if p not in chosen] or PRODUCTS
            if j == 0:
                pt = wpick([("Credit Card", 35), ("Personal Loan", 30),
                            ("BNPL", 15), ("Two-wheeler Loan", 10), ("Gold Loan", 10)])
            else:
                pt = pick(pool)
            chosen.append(pt)
        # Amit Verma's personal loan must exist (email cites Rs 24,500 EMI).
        if c["name"] == "Amit Verma" and "Personal Loan" not in chosen:
            chosen[0] = "Personal Loan"
        weights = [rng.random() + 0.5 for _ in range(n)]
        total_w = sum(weights)
        sanc = [max(15000, round(c["credit_limit"] * w / total_w / 1000) * 1000)
                for w in weights]
        sanc[-1] = c["credit_limit"] - sum(sanc[:-1])
        cust_acc = []
        # Hand-planned customers need enough monthly dues to exist for every
        # (account_position, due_position) entry in their late plan.
        back_min = 45
        if c["late_plan"] != "auto":
            max_dpos = max([d for _, d, _ in c["late_plan"]] + [0])
            back_min = {0: 15, 1: 45, 2: 76, 3: 107, 4: 137, 5: 168}[max_dpos] + 30
        elif c["behavior_profile"] == "delinquent":
            back_min = 168 + 30  # auto delinquents need 6 dues for 4-6 late rows
        for j, pt in enumerate(chosen):
            aid = f"ACC-{seq:03d}"
            seq += 1
            opened = ANCHOR - timedelta(
                days=rint(back_min, max(back_min, c["tenure_months"] * 30)))
            cust_acc.append(dict(account_id=aid, customer_id=c["customer_id"],
                                 product_type=pt, sanctioned_limit=sanc[j],
                                 opened_date=opened, status="Active",
                                 outstanding=0))
        # Oldest account of some long-tenure generated customers is Closed.
        if (c["late_plan"] == "auto" and c["tenure_months"] >= 36
                and n >= 2 and rng.random() < 0.25):
            oldest = min(cust_acc, key=lambda a: a["opened_date"])
            oldest["status"] = "Closed"
        # Outstanding split across non-closed accounts, matching utilization.
        live = [a for a in cust_acc if a["status"] != "Closed"]
        target = round(c["credit_limit"] * c["utilization_pct"] / 100)
        if live and target > 0:
            w = [rng.random() + 0.5 for _ in live]
            tw = sum(w)
            outs = [round(target * x / tw) for x in w]
            outs[-1] = target - sum(outs[:-1])
            for a, o in zip(live, outs):
                a["outstanding"] = max(0, o)
        accounts.extend(cust_acc)
    return accounts


# ---------------------------------------------------------------- repayments
DUE_MONTHS = [(2026, 10), (2026, 9), (2026, 8), (2026, 7), (2026, 6), (2026, 5)]
EMI_RANGE = {"Personal Loan": (12000, 45000), "Two-wheeler Loan": (3000, 9000),
             "Gold Loan": (5000, 20000), "Credit Card": (4000, 25000),
             "BNPL": (2000, 12000)}


def build_repayments(customers, accounts):
    by_cust = {}
    for a in accounts:
        by_cust.setdefault(a["customer_id"], []).append(a)

    # Dues per account: 1st of month, up to 6 back, only after account opened.
    dues = {}
    for a in accounts:
        c = next(c for c in customers if c["customer_id"] == a["customer_id"])
        cands = [date(y, m, 1) for y, m in DUE_MONTHS[:min(6, max(2, c["tenure_months"]))]]
        dues[a["account_id"]] = [d for d in cands
                                 if d >= a["opened_date"] + timedelta(days=10)]

    # Late plans: (account_id, due_date) -> "unpaid" | days_late int.
    plans = {}
    for c in customers:
        accs = sorted(by_cust[c["customer_id"]], key=lambda a: a["account_id"])
        live = [a for a in accs if a["status"] != "Closed"]
        if c["late_plan"] == "auto":
            pairs = [(a["account_id"], d) for a in live for d in dues[a["account_id"]]]
            pairs.sort(key=lambda p: p[1], reverse=True)
            plan = auto_plan(c["behavior_profile"], pairs)
        else:
            plan = {}
            for apos, dpos, late in c["late_plan"]:
                a = live[apos]
                d = dues[a["account_id"]][dpos]
                plan[(a["account_id"], d)] = late
        plans[c["customer_id"]] = plan

    rows = []
    seq = 1
    for c in customers:
        plan = plans[c["customer_id"]]
        late_days_list = []
        for a in sorted(by_cust[c["customer_id"]], key=lambda x: x["account_id"]):
            if a["status"] == "Closed":
                continue
            lo, hi = EMI_RANGE[a["product_type"]]
            emi = 24500 if (c["name"] == "Amit Verma"
                            and a["product_type"] == "Personal Loan") else rint(lo, hi)
            for d in dues[a["account_id"]]:
                late = plan.get((a["account_id"], d), 0)
                amt_due = (round(emi * rng.uniform(0.85, 1.15) / 100) * 100
                           if a["product_type"] == "Credit Card" else emi)
                if late == "unpaid":
                    paid, amt_paid = "", 0
                    dl = (ANCHOR - d).days
                elif late:
                    paid, amt_paid = iso(d + timedelta(days=late)), amt_due
                    dl = late
                else:
                    paid = iso(d - timedelta(days=rint(0, 2)))
                    amt_paid, dl = amt_due, 0
                if late:
                    late_days_list.append(dl)
                rows.append(dict(repayment_id=f"REP-{seq:04d}",
                                 account_id=a["account_id"], due_date=iso(d),
                                 paid_date=paid, amount_due=amt_due,
                                 amount_paid=amt_paid, days_late=dl))
                seq += 1
        c["missed_payments_12m"] = min(8, len(late_days_list))
        c["avg_days_late"] = (math.floor(sum(late_days_list) / len(late_days_list) + 0.5)
                              if late_days_list else 0)
        c["products_held"] = len(by_cust[c["customer_id"]])
    rows.sort(key=lambda r: (r["due_date"], r["account_id"]))
    return rows


def auto_plan(profile, pairs):
    """pairs: [(account_id, due_date)] recent-first. Returns {(acc, due): late}."""
    plan = {}

    def take(k, start=0):
        return pairs[start:start + k]

    if profile == "delinquent":
        k = rint(4, 6)
        if rng.random() < 0.5:  # deep: recent dues unpaid -> high current DPD
            sel = take(k)
            n_unpaid = rint(2, 3)
            for i, (a, d) in enumerate(sel):
                plan[(a, d)] = "unpaid" if i < n_unpaid else rint(8, 40)
        else:  # recovering: older dues paid late, nothing currently overdue
            for a, d in take(k, start=2):
                plan[(a, d)] = rint(10, 45)
    elif profile == "at-risk":
        for i, (a, d) in enumerate(take(rint(1, 3))):
            plan[(a, d)] = ("unpaid" if (i == 0 and rng.random() < 0.3)
                            else rint(5, 25))
    elif profile == "loyal":
        for a, d in take(rint(0, 1)):
            plan[(a, d)] = rint(3, 12)
    elif profile == "new":
        for a, d in take(rint(0, 1)):
            plan[(a, d)] = "unpaid" if rng.random() < 0.5 else rint(3, 15)
    elif profile == "dormant":
        for a, d in take(rint(0, 1)):
            plan[(a, d)] = rint(3, 10)
    elif profile == "high-value":
        for a, d in take(rint(0, 2)):
            plan[(a, d)] = rint(3, 18)
    return plan


# ---------------------------------------------------------------- transactions
CATS = [("Shopping", 35), ("Travel", 12), ("Bills", 25),
        ("Cash Withdrawal", 8), ("EMI Debit", 20)]
CHANNELS = {
    "Shopping": [("Online", 50), ("POS", 35), ("App", 15)],
    "Travel": [("Online", 70), ("App", 20), ("POS", 10)],
    "Bills": [("App", 50), ("Online", 40), ("POS", 10)],
    "Cash Withdrawal": [("POS", 80), ("App", 20)],
    "EMI Debit": [("App", 60), ("Online", 40)],
}
AMT = {"Shopping": (500, 60000), "Travel": (3000, 90000),
       "Bills": (400, 20000), "Cash Withdrawal": (2000, 40000),
       "EMI Debit": (4000, 60000)}


def build_transactions(customers, accounts):
    cmap = {c["customer_id"]: c for c in customers}
    # Two generated at-risk customers get sparse early-window activity.
    sparse_ids = set()
    cand = [c["customer_id"] for c in customers
            if c["behavior_profile"] == "at-risk" and c["late_plan"] == "auto"]
    rng.shuffle(cand)
    sparse_ids.update(cand[:2])

    rows = []
    seq = 1
    span = (ANCHOR - WINDOW_START).days
    for a in sorted(accounts, key=lambda x: x["account_id"]):
        if a["status"] == "Closed":
            continue
        c = cmap[a["customer_id"]]
        if c["behavior_profile"] == "dormant":
            continue  # dormant: nothing in the 90-day window
        if a["customer_id"] in sparse_ids:
            n, day_lo, day_hi = 3, 0, 29
        else:
            n, day_lo, day_hi = rint(11, 17), 0, span
        for _ in range(n):
            d = WINDOW_START + timedelta(days=rint(day_lo, day_hi))
            cat = wpick(CATS)
            lo, hi = AMT[cat]
            amt = rint(lo, hi)
            if cat == "Cash Withdrawal":
                amt = round(amt / 500) * 500
            rows.append(dict(txn_id=f"TXN-{seq:04d}", account_id=a["account_id"],
                             txn_date=iso(d), amount=amt, category=cat,
                             channel=wpick(CHANNELS[cat])))
            seq += 1
    rows.sort(key=lambda r: (r["txn_date"], r["txn_id"]))
    # Renumber after sort so TXN ids run in date order.
    for i, r in enumerate(rows, start=1):
        r["txn_id"] = f"TXN-{i:04d}"
    return rows


# ---------------------------------------------------------------- writers
CUSTOMER_COLS = ["customer_id", "name", "segment", "region", "tenure_months",
                 "credit_score", "credit_limit", "utilization_pct",
                 "missed_payments_12m", "avg_days_late", "products_held",
                 "lifetime_value", "behavior_profile", "contact_email",
                 "contact_phone"]
ACCOUNT_COLS = ["account_id", "customer_id", "product_type", "sanctioned_limit",
                "outstanding", "status", "opened_date"]
TXN_COLS = ["txn_id", "account_id", "txn_date", "amount", "category", "channel"]
REPAY_COLS = ["repayment_id", "account_id", "due_date", "paid_date",
              "amount_due", "amount_paid", "days_late"]


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- transcripts
TRANSCRIPTS = [
    dict(cid="CUST-001", name="Rohan Khanna", date="2026-10-02",
         kind="Inbound call", signal="complaint", lines=[
        ("Agent", "Good morning, Mr. Khanna. This is Arjun Mehta, your relationship manager. How can I help you today?"),
        ("Customer", "Arjun, I am quite upset. I was promised a lifetime-free card when I joined five years ago, and now I see a Rs 5,000 annual fee on my September statement."),
        ("Agent", "I am sorry to hear that, sir. Let me pull up your account. Yes, I can see the fee posted on September 28th. Your 2021 onboarding does carry the lifetime-free tag."),
        ("Customer", "Exactly. I spend over a lakh every month on this card. Charging me a fee after five loyal years feels like a betrayal."),
        ("Agent", "I completely understand, and you are right to flag it. This looks like a system error during the September fee run."),
        ("Customer", "I want it reversed, Arjun. And I want an assurance it will not happen again."),
        ("Agent", "Consider it done, sir. I am raising a fee-reversal request right now, and I will personally make sure the lifetime-free tag is locked on your account."),
        ("Customer", "Thank you. I was honestly considering moving my spends to another bank's card."),
        ("Agent", "I am glad you called before doing that, sir. You will get the reversal confirmation by SMS within 48 hours. Anything else I can help with?"),
        ("Customer", "No, that is all. Please make sure this is sorted."),
    ]),
    dict(cid="CUST-003", name="Amit Verma", date="2026-09-28",
         kind="Inbound call", signal="dispute-open", lines=[
        ("Agent", "Good afternoon, Mr. Verma. Arjun Mehta here. What can I do for you?"),
        ("Customer", "Arjun, my September EMI of Rs 24,500 was debited twice, once on the 5th and again on the 7th. That is not right."),
        ("Agent", "Let me check. Yes, I can see two debits of Rs 24,500 on your loan account, two days apart. That does look like a duplicate posting."),
        ("Customer", "My salary account is now short, and my SIP bounced because of it. I need the extra debit reversed immediately."),
        ("Agent", "I understand the urgency, sir. I am logging this as a formal billing dispute right now. The ticket reference will come to you by SMS."),
        ("Customer", "How long will the reversal take? This is your system's mistake."),
        ("Agent", "For confirmed duplicate debits, the reversal usually credits within 5 to 7 working days, sir. I will also flag the bounced SIP charge for a goodwill waiver."),
        ("Customer", "Please do. And please make sure October's EMI goes through only once."),
        ("Agent", "Absolutely. I am also placing a watch on your account so the October debit is monitored. I will call you once the reversal is processed."),
        ("Customer", "Alright. I will wait for your update."),
    ]),
    dict(cid="CUST-005", name="Vikram Rao", date="2026-09-20",
         kind="Outbound call", signal="churn-risk", lines=[
        ("Agent", "Good evening, Mr. Rao. Arjun Mehta calling. It has been a while since we spoke. Is everything alright with your accounts?"),
        ("Customer", "Honestly, Arjun, I have barely used the card in months. Another bank is offering me much better travel rewards, and I am thinking of moving everything there."),
        ("Agent", "I appreciate your honesty, sir. You have been with us for over six years, and your payment record is spotless. May I ask what is driving the switch?"),
        ("Customer", "It is simple math, 2% more on travel spends and free lounge access. Your card gives me nothing for the spends I actually make."),
        ("Agent", "That is fair feedback. Before you decide, would you be open to a quick review? I can look at your spend pattern and see if we have a variant that matches it better."),
        ("Customer", "I have more or less made up my mind. Unless something changes materially, I will be closing the card next month."),
        ("Agent", "Understood, sir. I would still like our senior team to speak with you once, a short callback this week at your convenience. Would Thursday work?"),
        ("Customer", "Fine, Thursday evening. But I am not making any promises."),
        ("Agent", "Noted, sir. I will schedule it. Thank you for your time."),
        ("Customer", "Alright, bye."),
    ]),
    dict(cid="CUST-004", name="Kavya Nair", date="2026-10-04",
         kind="Inbound call", signal="upsell-window", lines=[
        ("Agent", "Good morning, Ms. Nair. Arjun Mehta here. How may I help you?"),
        ("Customer", "Hi Arjun. I am planning a home renovation next month, around six lakhs. I wanted to check if I can get a top-up on my existing personal loan."),
        ("Agent", "That is a good question, ma'am. Your repayment record is excellent, and your current utilization is quite low, which works in your favour."),
        ("Customer", "What would the top-up amount and rate look like? I do not want to stretch my EMI too much."),
        ("Agent", "Based on your profile, a top-up of up to Rs 4 lakh looks feasible, likely at a rate better than your current loan. I can get you a firm offer letter."),
        ("Customer", "That sounds promising. Would it be a separate loan or merged with the existing one?"),
        ("Agent", "We can structure it either way, ma'am. Most customers prefer merging it into a single EMI for simplicity."),
        ("Customer", "Alright, please send me the offer details. If the numbers work, I will go ahead this month itself."),
        ("Agent", "I will have the pre-approved offer on your email by tomorrow evening, ma'am. Anything else?"),
        ("Customer", "No, that is it. Thanks, Arjun."),
    ]),
    dict(cid="CUST-002", name="Sneha Iyer", date="2026-09-25",
         kind="Outbound call", signal="life-event", lines=[
        ("Agent", "Good afternoon, Ms. Iyer. This is Arjun Mehta. I am calling about your overdue payments. I wanted to understand your situation."),
        ("Customer", "Arjun, I will be honest. I lost my job in August. The company shut our entire division. I have been trying to manage, but the EMIs are piling up."),
        ("Agent", "I am very sorry to hear that, ma'am. Thank you for telling me, it helps us help you better. Are you currently looking for work?"),
        ("Customer", "Yes, I have had two interviews last week. I expect to join somewhere by November. I just need some breathing room till then."),
        ("Agent", "I understand. We do have a hardship programme. We can look at restructuring your dues or a short moratorium once we have your details."),
        ("Customer", "That would be a huge relief. I have every intention of paying, I just cannot do it this month."),
        ("Agent", "Noted, ma'am. I will send you the hardship application form today. Please fill it and share your termination letter, that speeds up approval."),
        ("Customer", "I will do that today itself. Thank you for not just threatening legal action like the last caller did."),
        ("Agent", "That is not how we work, ma'am. I will personally follow up next week. Take care."),
        ("Customer", "Thank you, Arjun. Bye."),
    ]),
    dict(cid="CUST-007", name="Aditya Kulkarni", date="2026-09-18",
         kind="Outbound call", signal="churn-risk", lines=[
        ("Agent", "Good morning, Mr. Kulkarni. Arjun Mehta here. I noticed your salary credits stopped coming to your linked account. Is everything okay?"),
        ("Customer", "I switched jobs last month, Arjun, and the new company banks elsewhere. Frankly, I am moving all my accounts there for convenience."),
        ("Agent", "Congratulations on the new role, sir. Before you move everything, could we discuss what matters most to you in a banking relationship?"),
        ("Customer", "It is about the little things, instant customer care, no paperwork. My experience here has been average."),
        ("Agent", "I hear you, and I would hate to lose you over service gaps we can fix. Would you keep the loan here if we assign you a dedicated service line?"),
        ("Customer", "The loan I can foreclose next quarter from my bonus. Then there is nothing tying me here."),
        ("Agent", "Understood. Let me have our retention specialist call you this week with a concrete proposal, no pressure, just options on paper."),
        ("Customer", "One call. That is all I will agree to."),
        ("Agent", "Fair enough, sir. I will set it up. Thank you for your time."),
        ("Customer", "Alright."),
    ]),
    dict(cid="CUST-008", name="Pooja Deshmukh", date="2026-09-30",
         kind="Inbound call", signal="dispute-open", lines=[
        ("Agent", "Good afternoon, Ms. Deshmukh. Arjun Mehta here. How can I assist you?"),
        ("Customer", "Hi Arjun. There is a Rs 18,200 electronics purchase on my card statement that I never made. I want to dispute it."),
        ("Agent", "I am sorry to hear that, ma'am. Let me note the details, Rs 18,200, posted on September 22nd, merchant listed as an online electronics store?"),
        ("Customer", "Yes. I have not bought any electronics this year. Someone must have used my card details."),
        ("Agent", "I will raise a dispute for this transaction immediately, ma'am, and issue you a replacement card with a new number as a precaution."),
        ("Customer", "Will I have to pay this amount while the dispute is investigated?"),
        ("Agent", "No, ma'am. The disputed amount is kept on hold, you do not pay it while the investigation is open. I will confirm that in writing today."),
        ("Customer", "Good. How long does the investigation take?"),
        ("Agent", "Typically 30 to 45 days, ma'am. I will personally track it and update you at each stage."),
        ("Customer", "Thank you, Arjun. Please make sure the replacement card reaches me soon."),
    ]),
    dict(cid="CUST-009", name="Karan Malhotra", date="2026-10-01",
         kind="Inbound call", signal="complaint", lines=[
        ("Agent", "Good morning, Mr. Malhotra. Arjun Mehta here. What can I do for you today?"),
        ("Customer", "Arjun, I got a collection call at 9 pm last night, and the caller was rude. He said my account would be reported everywhere if I did not pay immediately."),
        ("Agent", "I am very sorry, sir. That is not acceptable, and it is not how our team is trained to speak. Let me look into this right away."),
        ("Customer", "I was two weeks late, not two years. There is a way to talk to people, and that was not it."),
        ("Agent", "You are absolutely right, sir. I will pull the call recording from last night and escalate this to the collections supervisor today."),
        ("Customer", "I want an apology, and I want an assurance that I will not get calls after 7 pm."),
        ("Agent", "You will have both, sir. I will also make sure your account is marked so all future communication goes through me directly."),
        ("Customer", "Alright. I have cleared the overdue amount this morning, by the way."),
        ("Agent", "Thank you, sir, I can see the payment reflecting. I will call you back tomorrow with an update on the escalation."),
        ("Customer", "Fine. I expect this to be taken seriously."),
    ]),
    dict(cid="CUST-010", name="Ananya Reddy", date="2026-09-22",
         kind="Outbound call", signal="life-event", lines=[
        ("Agent", "Good morning, Ms. Reddy. Arjun Mehta calling. I wanted to check in, I see your last EMI came in a little late."),
        ("Customer", "Hi Arjun. Yes, I had my baby last month, and with the hospital bills and everything, this month just got away from me."),
        ("Agent", "Congratulations, ma'am! And please do not worry, one slightly late payment is completely understandable in your situation."),
        ("Customer", "Thank you. My husband and I have planned the finances, but the medical expenses were higher than we expected."),
        ("Agent", "I understand. Would a short EMI deferral for a month or two help you settle in? We can restructure without hurting your record."),
        ("Customer", "That would actually help a lot. Just a month's breather would be enough."),
        ("Agent", "Consider it noted, ma'am. I will send the deferral request form today, it is a simple one-page process."),
        ("Customer", "Thanks, Arjun. I will make sure October's payment is on time."),
        ("Agent", "Take care of yourself and the little one, ma'am. I will follow up next week."),
        ("Customer", "Thank you. Bye."),
    ]),
    dict(cid="CUST-011", name="Suresh Pillai", date="2026-10-05",
         kind="Inbound call", signal="upsell-window", lines=[
        ("Agent", "Good afternoon, Mr. Pillai. Arjun Mehta here. How can I help you?"),
        ("Customer", "Arjun, my business is expanding, I am opening a second outlet next quarter. I need to increase my credit limit for stock purchases."),
        ("Agent", "That is great news, sir. Given your clean repayment history and low utilization, a limit enhancement looks very possible."),
        ("Customer", "My current limit is Rs 6 lakh. I would need it closer to 10 for the new outlet's inventory."),
        ("Agent", "That is a reasonable ask, sir. I will run a fresh assessment and come back with an enhanced limit offer, possibly with a business top-up loan as an alternative."),
        ("Customer", "What is the turnaround time? I need to place orders by month-end."),
        ("Agent", "The assessment takes about three working days, sir. I will personally make sure your file is prioritized."),
        ("Customer", "Good. Also, will this affect my existing EMI schedule?"),
        ("Agent", "Not at all, sir, the enhancement sits on top of your current structure. I will explain both options when I call back."),
        ("Customer", "Perfect. I will wait for your call."),
    ]),
]


def write_transcripts():
    parts = ["# RelateIQ - Call Transcripts (Sep-Oct 2026)",
             "",
             "> Synthetic demo data. All customers, conversations and signals are fictional.",
             ""]
    for t in sorted(TRANSCRIPTS, key=lambda t: t["cid"]):
        parts.append(f"## {t['cid']} - {t['name']}")
        parts.append(f"**Date:** {t['date']} | **Type:** {t['kind']} | "
                     f"**Agent:** Arjun Mehta (Relationship Manager)")
        parts.append("")
        for role, line in t["lines"]:
            parts.append(f"{role}: {line}")
        parts.append("")
        parts.append(f"[SIGNAL: {t['signal']}]")
        parts.append("")
        parts.append("---")
        parts.append("")
    (OUT / "call_transcripts.md").write_text("\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------- emails
EMAILS = [
    dict(cid="CUST-003", name="Amit Verma", signal="dispute-open",
         subject="Double EMI debit in September - reversal requested",
         messages=[
        ("amit.verma@examplemail.com", "2026-09-14",
         "Dear Team,\n\nMy September EMI of Rs 24,500 towards my personal loan was "
         "debited twice, on 5th Sep and again on 7th Sep. This is clearly a system "
         "error. Because of the extra debit, my monthly SIP also bounced. Please "
         "reverse the duplicate debit immediately and confirm.\n\nRegards,\nAmit Verma"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-15",
         "Dear Mr. Verma,\n\nThank you for writing in. We have verified the duplicate "
         "debit on your loan account and raised dispute ticket DSP-2026-8841. The "
         "excess Rs 24,500 will be reversed to your account within 5 to 7 working "
         "days. As a goodwill gesture, we are also waiving the SIP bounce charge "
         "caused by this error.\n\nRegards,\nArjun Mehta, Relationship Manager"),
        ("amit.verma@examplemail.com", "2026-09-16",
         "Thanks for the quick response, Arjun. Please confirm once the reversal is "
         "credited, and kindly ensure the October EMI is debited only once.\n\nRegards,\nAmit"),
    ]),
    dict(cid="CUST-001", name="Rohan Khanna", signal="complaint",
         subject="Annual fee charged despite lifetime-free card",
         messages=[
        ("rohan.khanna@examplemail.com", "2026-09-29",
         "Dear Team,\n\nI am writing to complain about a Rs 5,000 annual fee charged "
         "on my September credit card statement. When I took this card in 2021, I was "
         "promised it would be lifetime-free. I have been a loyal customer for five "
         "years with monthly spends above a lakh. This fee is unacceptable. I expect "
         "an immediate reversal and a written assurance it will not recur.\n\nRegards,\nRohan Khanna"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-30",
         "Dear Mr. Khanna,\n\nPlease accept our sincere apologies. I have verified "
         "your 2021 onboarding record, which carries the lifetime-free tag. The fee "
         "was posted in error during the September fee cycle. I have raised the "
         "reversal, which will reflect within 48 hours, and locked the lifetime-free "
         "tag on your account so this cannot happen again.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
    dict(cid="CUST-005", name="Vikram Rao", signal="churn-risk",
         subject="Request to review my card before I decide",
         messages=[
        ("vikram.rao@examplemail.com", "2026-09-19",
         "Dear Team,\n\nI have been thinking about my credit card. I barely use it "
         "now, and another bank is offering me far better travel rewards with lounge "
         "access. After six years, the card no longer fits my spending. Before I "
         "close it, I wanted to give you a chance to respond.\n\nRegards,\nVikram Rao"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-20",
         "Dear Mr. Rao,\n\nThank you for reaching out before deciding. Your six-year "
         "spotless record matters to us. I would like our senior team to speak with "
         "you once, this Thursday evening, to review your spend pattern and discuss "
         "a card variant that may suit you better. Please let me know if Thursday "
         "works.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
    dict(cid="CUST-004", name="Kavya Nair", signal="upsell-window",
         subject="Top-up loan enquiry for home renovation",
         messages=[
        ("kavya.nair@examplemail.com", "2026-09-30",
         "Dear Arjun,\n\nI am planning a home renovation next month with a budget of "
         "around six lakhs. Could I get a top-up on my existing personal loan? I "
         "would like to understand the eligible amount, the rate, and whether it "
         "merges with my current EMI.\n\nRegards,\nKavya Nair"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-30",
         "Dear Ms. Nair,\n\nThank you for your enquiry. Given your excellent "
         "repayment record, a pre-approved top-up of up to Rs 4 lakh is being "
         "prepared, likely at a rate better than your current loan. It can be merged "
         "into a single EMI. I will email the firm offer letter by tomorrow "
         "evening.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
    dict(cid="CUST-002", name="Sneha Iyer", signal="life-event",
         subject="Request for payment relief - job loss",
         messages=[
        ("sneha.iyer@examplemail.com", "2026-09-24",
         "Dear Team,\n\nI am writing with difficulty. I lost my job in August when "
         "our entire division was shut down. I have attended interviews and hope to "
         "join a new company by November, but I cannot make my payments this month. "
         "I fully intend to repay. Please advise if you have a hardship programme or "
         "a way to restructure my dues.\n\nRegards,\nSneha Iyer"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-25",
         "Dear Ms. Iyer,\n\nI am sorry to hear about your situation, and I appreciate "
         "your honesty. We do have a hardship programme that can offer a short "
         "moratorium or a restructured plan. I have attached the application form. "
         "Please return it with your termination letter, which will speed up "
         "approval. I will personally follow up next week.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
    dict(cid="CUST-007", name="Aditya Kulkarni", signal="churn-risk",
         subject="Moving my accounts - closure procedure",
         messages=[
        ("aditya.kulkarni@examplemail.com", "2026-09-17",
         "Dear Team,\n\nI have switched jobs and my new employer banks elsewhere. I "
         "am moving all my accounts there for convenience. Please share the procedure "
         "to foreclose my personal loan next quarter.\n\nRegards,\nAditya Kulkarni"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-18",
         "Dear Mr. Kulkarni,\n\nCongratulations on the new role. Before you move "
         "everything, I would like our retention specialist to speak with you once "
         "and share concrete options, including a dedicated service line for your "
         "loan. Could we schedule a short call this week?\n\nRegards,\nArjun Mehta, Relationship Manager"),
        ("aditya.kulkarni@examplemail.com", "2026-09-18",
         "One call. That is all I will agree to.\n\nRegards,\nAditya"),
    ]),
    dict(cid="CUST-008", name="Pooja Deshmukh", signal="dispute-open",
         subject="Fraudulent transaction of Rs 18,200 - dispute",
         messages=[
        ("pooja.deshmukh@examplemail.com", "2026-09-28",
         "Dear Team,\n\nA transaction of Rs 18,200 at an online electronics store "
         "appears on my September card statement, posted on 22nd Sep. I did not make "
         "this purchase. Please treat this as a fraud dispute, block my card, and "
         "issue a replacement.\n\nRegards,\nPooja Deshmukh"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-29",
         "Dear Ms. Deshmukh,\n\nI am sorry this happened. I have raised a dispute "
         "for the Rs 18,200 transaction. The disputed amount is on hold and is not "
         "payable while the investigation, typically 30 to 45 days, is open. A "
         "replacement card with a new number has been dispatched. I will update you "
         "at each stage.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
    dict(cid="CUST-009", name="Karan Malhotra", signal="complaint",
         subject="Rude collection call at 9 pm - formal complaint",
         messages=[
        ("karan.malhotra@examplemail.com", "2026-09-29",
         "Dear Team,\n\nI wish to formally complain about a collection call I "
         "received at 9 pm last night. The caller was rude and threatened that my "
         "account would be reported everywhere if I did not pay immediately. I was "
         "two weeks late, not two years. I expect an apology and an assurance that I "
         "will not receive calls after 7 pm.\n\nRegards,\nKaran Malhotra"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-30",
         "Dear Mr. Malhotra,\n\nPlease accept my sincere apology. This is not how "
         "our team is trained to speak. I have pulled last night's call recording "
         "and escalated it to the collections supervisor. All future communication "
         "on your account will come through me directly, and within calling "
         "hours.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
    dict(cid="CUST-010", name="Ananya Reddy", signal="life-event",
         subject="EMI deferral request - maternity",
         messages=[
        ("ananya.reddy@examplemail.com", "2026-09-21",
         "Dear Arjun,\n\nI had my baby last month, and with the hospital bills, this "
         "month's finances slipped. Could I get a one-month breather on my EMI? Just "
         "a short deferral would help us settle in.\n\nRegards,\nAnanya Reddy"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-22",
         "Dear Ms. Reddy,\n\nCongratulations on the new arrival! A one-month "
         "deferral is absolutely possible and will not hurt your record. I have "
         "attached a simple one-page form. Please return it at your "
         "convenience.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
    dict(cid="CUST-011", name="Suresh Pillai", signal="upsell-window",
         subject="Credit limit enhancement for business expansion",
         messages=[
        ("suresh.pillai@examplemail.com", "2026-09-28",
         "Dear Arjun,\n\nMy business is expanding and I am opening a second outlet "
         "next quarter. I need my credit limit enhanced from Rs 6 lakh to around Rs "
         "10 lakh for inventory purchases. I must place orders by month-end, so I "
         "would appreciate a quick assessment.\n\nRegards,\nSuresh Pillai"),
        ("Arjun Mehta <arjun.mehta@relateiq.example.com>", "2026-09-29",
         "Dear Mr. Pillai,\n\nCongratulations on the expansion. Given your clean "
         "repayment history, a limit enhancement looks very possible. I have "
         "initiated the assessment, which takes about three working days, and marked "
         "your file as priority. I will call you with the offer and the structuring "
         "options.\n\nRegards,\nArjun Mehta, Relationship Manager"),
    ]),
]


def write_emails():
    parts = ["# RelateIQ - Support Email Threads (Sep 2026)",
             "",
             "> Synthetic demo data. All customers, threads and signals are fictional.",
             ""]
    for e in sorted(EMAILS, key=lambda e: e["cid"]):
        parts.append(f"## {e['cid']} - {e['name']}")
        parts.append(f"**Subject:** {e['subject']}")
        parts.append("")
        for i, (sender, dt, body) in enumerate(e["messages"]):
            parts.append(f"**From:** {sender} | **Date:** {dt}")
            parts.append("")
            parts.append(body)
            parts.append("")
            if i < len(e["messages"]) - 1:
                parts.append("---")
                parts.append("")
        parts.append(f"[SIGNAL: {e['signal']}]")
        parts.append("")
        parts.append("---")
        parts.append("")
    (OUT / "support_emails.md").write_text("\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------- main
def main():
    customers = build_customers()
    accounts = build_accounts(customers)
    repayments = build_repayments(customers, accounts)
    transactions = build_transactions(customers, accounts)

    write_csv(OUT / "customers.csv", CUSTOMER_COLS, customers)
    write_csv(OUT / "accounts.csv", ACCOUNT_COLS, accounts)
    write_csv(OUT / "transactions.csv", TXN_COLS, transactions)
    write_csv(OUT / "repayments.csv", REPAY_COLS, repayments)
    write_transcripts()
    write_emails()

    print(f"customers:    {len(customers)}")
    print(f"accounts:     {len(accounts)}")
    print(f"transactions: {len(transactions)}")
    print(f"repayments:   {len(repayments)}")
    print(f"transcripts:  {len(TRANSCRIPTS)} customers")
    print(f"email threads:{len(EMAILS)} customers")


if __name__ == "__main__":
    main()
