import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "week3"))

from analyze_findings import build_comparison, classify_findings


class Week3FindingAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.verification = [
            {
                "outcome": "CONFIRMED_USER_TO_USER_BOLA",
                "actor_role": "userB",
                "owner_role": "userA",
                "fixture_id": "userA-book",
                "status_code": 200,
                "secret_matches_fresh_owner_baseline": True,
            },
            {
                "outcome": "POLICY_DEPENDENT_ADMIN_ACCESS",
                "actor_role": "admin",
                "owner_role": "userA",
                "fixture_id": "userA-book",
                "status_code": 200,
                "secret_matches_fresh_owner_baseline": True,
            },
        ]
        self.inventory = [
            {
                "is_bfla_candidate": True,
                "state_changing": True,
                "method": "DELETE",
                "path": "/users/v1/{username}",
            }
        ]

    def test_keeps_admin_access_policy_dependent(self):
        findings = classify_findings(self.verification, self.inventory)
        self.assertEqual(findings[0]["status"], "CONFIRMED")
        self.assertEqual(findings[0]["evidence_count"], 1)
        self.assertEqual(findings[1]["status"], "POLICY_DEPENDENT")
        self.assertEqual(findings[1]["evidence_count"], 1)

    def test_marks_unexecuted_bfla_as_not_executed(self):
        findings = classify_findings(self.verification, self.inventory)
        self.assertEqual(findings[2]["classification"], "BFLA")
        self.assertEqual(findings[2]["status"], "NOT_EXECUTED")

    def test_comparison_leaves_manual_data_pending(self):
        comparison = build_comparison(
            {"elapsed_ms": 2000.0, "case_count": 12},
            self.verification,
            {"status": "NOT_RUN", "finding_count": None},
        )
        self.assertEqual(comparison["manual_postman_or_burp"]["status"], "PENDING_HUMAN_MEASUREMENT")
        self.assertIsNone(comparison["manual_postman_or_burp"]["elapsed_minutes"])
        self.assertEqual(comparison["owasp_zap"]["status"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
