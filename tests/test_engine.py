#!/usr/bin/env python3
"""RelateIQ engine determinism + decision-branch test suite.

Stdlib unittest only (no new dependencies). Runs against app/engine.py with
hand-built fixtures in the exact SPEC schema shape, so every branch threshold
is exercised deliberately.

Run from repo root:
    python3 -m unittest discover -s tests -v
or:
    python3 tests/test_engine.py
"""
import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import engine


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def make_cust(customer_id="CUST-T01", name="Test One", **over):
    """Customer row with healthy defaults; override per test."""
    cust = {
        "customer_id": customer_id,
        "name": name,
        "segment": "Salaried",
        "region": "Mumbai",
        "tenure_months": "36",
        "credit_score": "720",
        "credit_limit": "500000",
        "utilization_pct": "25",
        "missed_payments_12m": "0",
        "avg_days_late": "0",
        "products_held": "1",
        "lifetime_value": "100000",
        "behavior_profile": "loyal",
        "contact_email": "test.one@examplemail.com",
        "contact_phone": "+91 98000 00001",
    }
    cust.update(over)
    return cust


def unpaid_repayment(due_date):
    return {"repayment_id": "R-T", "account_id": "ACC-T",
            "due_date": due_date, "paid_date": "",
            "amount_due": "10000", "amount_paid": "0", "days_late": "0"}


def recent_txn():
    return {"txn_id": "T-T", "account_id": "ACC-T",
            "txn_date": "2026-10-05", "amount": "5000",
            "category": "Shopping", "channel": "App"}


def score_and_decide(cust, repayments=(), txns=(recent_txn(),), signals=()):
    """Full pipeline for one fixture customer: score -> decide."""
    txns = list(txns)
    repayments = list(repayments)
    attention, opportunity, trace = engine.score_customer(
        cust, [], repayments, txns, list(signals))
    dpd = engine.current_dpd(repayments)
    action, reason, draft = engine.decide(
        cust, attention, opportunity, list(signals), dpd)
    return {
        "attention": attention, "opportunity": opportunity, "trace": trace,
        "dpd": dpd, "action": action, "reason": reason, "draft": draft,
    }


# ---------------------------------------------------------------------------
# Decision branches
# ---------------------------------------------------------------------------

class TestDecisionBranches(unittest.TestCase):

    def test_dispute_beats_churn(self):
        """dispute-open + churn-risk -> dispute-hold (dispute always wins)."""
        cust = make_cust(lifetime_value="300000")  # high enough for churn branch
        r = score_and_decide(cust, signals=["dispute-open", "churn-risk"])
        self.assertEqual(r["action"], "dispute-hold")
        self.assertIn("dispute", r["reason"].lower())

    def test_dispute_beats_collections(self):
        """dispute-open + severe delinquency -> dispute-hold."""
        cust = make_cust(missed_payments_12m="5")
        r = score_and_decide(
            cust,
            repayments=[unpaid_repayment("2026-08-22")],  # DPD 45 -> firm territory
            signals=["dispute-open"],
        )
        self.assertGreater(r["dpd"], 30)
        self.assertEqual(r["action"], "dispute-hold")

    def test_churn_risk_only_gets_human_callback(self):
        """churn-risk alone (high LTV, clean books) -> churn-intervention."""
        cust = make_cust(lifetime_value="300000")
        r = score_and_decide(cust, signals=["churn-risk"])
        self.assertEqual(r["action"], "churn-intervention")
        self.assertIn("callback", r["draft"].lower())

    def test_severe_delinquency_firm(self):
        """DPD 45 -> collections-firm."""
        cust = make_cust()
        r = score_and_decide(cust, repayments=[unpaid_repayment("2026-08-22")])
        self.assertEqual(r["dpd"], 45)
        self.assertEqual(r["action"], "collections-firm")

    def test_severe_missed_history_firm(self):
        """4+ missed payments in 12m (even DPD 0) -> collections-firm."""
        cust = make_cust(missed_payments_12m="4")
        r = score_and_decide(cust)
        self.assertEqual(r["dpd"], 0)
        self.assertEqual(r["action"], "collections-firm")

    def test_mild_delinquency_gentle(self):
        """DPD 10, low missed history -> collections-gentle."""
        cust = make_cust(missed_payments_12m="1")
        r = score_and_decide(cust, repayments=[unpaid_repayment("2026-09-26")])
        self.assertEqual(r["dpd"], 10)
        self.assertEqual(r["action"], "collections-gentle")

    def test_retention_offer_on_complaint(self):
        """Unresolved complaint + high LTV + zero DPD -> retention-offer."""
        cust = make_cust(lifetime_value="300000")
        r = score_and_decide(cust, signals=["complaint"])
        self.assertEqual(r["dpd"], 0)
        self.assertEqual(r["action"], "retention-offer")

    def test_upsell_when_eligible(self):
        """No blockers + opportunity >= 70 + attention < 30 -> upsell."""
        cust = make_cust(
            credit_score="780", utilization_pct="20",
            missed_payments_12m="0", tenure_months="36")
        r = score_and_decide(cust, signals=["upsell-window"])
        self.assertGreaterEqual(r["opportunity"], 70)
        self.assertLess(r["attention"], 30)
        self.assertEqual(r["action"], "upsell")
        self.assertIn("pre-approved", r["draft"].lower())

    def test_monitor_fallback(self):
        """Healthy customer, no signals, opportunity below bar -> monitor."""
        r = score_and_decide(make_cust(utilization_pct="55"))
        self.assertLess(r["opportunity"], 70)
        self.assertEqual(r["action"], "monitor")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism(unittest.TestCase):

    def _run(self, cust, signals):
        return score_and_decide(cust, repayments=[unpaid_repayment("2026-09-01")],
                                signals=signals)

    def test_same_customer_scored_twice_identical(self):
        """Same inputs twice -> identical scores, branch, and trace."""
        cust = make_cust(missed_payments_12m="2", utilization_pct="65",
                         credit_score="640", lifetime_value="220000")
        signals = ["churn-risk", "complaint"]
        r1 = self._run(cust, signals)
        r2 = self._run(cust, signals)
        self.assertEqual(r1["attention"], r2["attention"])
        self.assertEqual(r1["opportunity"], r2["opportunity"])
        self.assertEqual(r1["action"], r2["action"])
        self.assertEqual(r1["dpd"], r2["dpd"])
        self.assertEqual(r1["trace"], r2["trace"])
        self.assertEqual(r1["reason"], r2["reason"])
        self.assertEqual(r1["draft"], r2["draft"])

    def test_fixtures_pipeline_deterministic(self):
        """demo_fixtures() full pipeline is byte-identical across runs."""
        def snapshot():
            out = []
            for r in engine.run_pipeline(engine.demo_fixtures()):
                out.append((r["customer_id"], r["attention"], r["opportunity"],
                            r["action"], r["dpd"], tuple(r["trace"])))
            return out
        self.assertEqual(snapshot(), snapshot())


# ---------------------------------------------------------------------------
# Audit: exactly one row per decision
# ---------------------------------------------------------------------------

class TestAudit(unittest.TestCase):

    def _record(self, cust, action, attention=50, opportunity=40):
        return {
            "timestamp": "2026-10-06T09:00:00",
            "customer_id": cust["customer_id"],
            "action": action,
            "attention": attention,
            "opportunity": opportunity,
            "reason": "test reason",
        }

    def _rows(self, path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_one_decision_one_audit_row(self):
        """A single decision -> exactly one audit row with matching fields."""
        with tempfile.TemporaryDirectory() as d:
            engine.append_audit(d, self._record(make_cust(), "upsell"))
            rows = self._rows(os.path.join(d, "audit_log.csv"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["customer_id"], "CUST-T01")
            self.assertEqual(rows[0]["action"], "upsell")

    def test_n_decisions_n_rows_append_only(self):
        """Three decisions -> exactly three rows, in order, never rewritten."""
        with tempfile.TemporaryDirectory() as d:
            for i, action in enumerate(["dispute-hold", "collections-firm", "monitor"]):
                engine.append_audit(
                    d, self._record(make_cust(customer_id=f"CUST-T0{i + 1}"),
                                    action))
            rows = self._rows(os.path.join(d, "audit_log.csv"))
            self.assertEqual(len(rows), 3)
            self.assertEqual([r["action"] for r in rows],
                             ["dispute-hold", "collections-firm", "monitor"])
            self.assertEqual([r["customer_id"] for r in rows],
                             ["CUST-T01", "CUST-T02", "CUST-T03"])

    def test_audit_matches_decision(self):
        """End-to-end: decide() then one audit write -> row mirrors decision."""
        with tempfile.TemporaryDirectory() as d:
            cust = make_cust(lifetime_value="300000")
            r = score_and_decide(cust, signals=["dispute-open", "churn-risk"])
            engine.append_audit(d, {
                "timestamp": "2026-10-06T09:00:00",
                "customer_id": cust["customer_id"],
                "action": r["action"],
                "attention": r["attention"],
                "opportunity": r["opportunity"],
                "reason": r["reason"],
            })
            rows = self._rows(os.path.join(d, "audit_log.csv"))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["action"], "dispute-hold")
            self.assertEqual(int(rows[0]["attention"]), r["attention"])


# ---------------------------------------------------------------------------
# Signal parsing: missing / malformed transcripts must not crash
# ---------------------------------------------------------------------------

class TestSignalParsing(unittest.TestCase):

    def _parse(self, content):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return engine.parse_signal_markdown(path, {"Test One": "CUST-T01"})

    def test_missing_file_returns_empty(self):
        sigs, texts = engine.parse_signal_markdown(
            "/nonexistent/path/t.md", {"Test One": "CUST-T01"})
        self.assertEqual(sigs, {})
        self.assertEqual(texts, {})

    def test_empty_file_returns_empty(self):
        sigs, texts = self._parse("")
        self.assertEqual(sigs, {})
        self.assertEqual(texts, {})

    def test_no_headers_no_crash(self):
        sigs, texts = self._parse("Just some prose, no sections at all.\n")
        self.assertEqual(sigs, {})
        self.assertEqual(texts, {})

    def test_unknown_signal_tag_ignored(self):
        sigs, _ = self._parse(
            "## CUST-T01 - Test One\n\nCustomer says hi.\n\n[SIGNAL: bogus-tag]\n")
        self.assertNotIn("bogus-tag", sigs.get("CUST-T01", []))

    def test_unattributed_section_skipped(self):
        sigs, _ = self._parse(
            "## Mystery section\n\nNobody here.\n\n[SIGNAL: churn-risk]\n")
        self.assertEqual(sigs, {})

    def test_valid_tag_parsed_by_id(self):
        sigs, texts = self._parse(
            "## CUST-T01 - Test One\n\nCustomer wants to leave.\n\n"
            "[SIGNAL: churn-risk]\n")
        self.assertEqual(sigs.get("CUST-T01"), ["churn-risk"])
        self.assertIn("CUST-T01", texts)

    def test_structured_path_survives_malformed_transcript(self):
        """Missing/malformed transcript -> structured scoring still works."""
        sigs, _ = self._parse("garbage [[[\n## broken")
        signals = sigs.get("CUST-T01", [])
        r = score_and_decide(make_cust(), signals=signals)
        self.assertIsInstance(r["attention"], int)
        self.assertIsInstance(r["action"], str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
