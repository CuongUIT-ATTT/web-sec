"""Tests for week4.bfla_executor guardrail and findings builder."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# week4 is a package at the project root, same level as bfla_disposable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from week4.bfla_executor import (
    BflaGuardrailError,
    assert_disposable_target,
    run_bfla_week4,
    _build_findings,
)


class AssertDisposableTargetTests(unittest.TestCase):
    """Guardrail: reject known fixtures, accept only disposable patterns."""

    def test_refuses_known_fixture_username_userA(self):
        with self.assertRaises(BflaGuardrailError):
            assert_disposable_target("userA")

    def test_refuses_known_fixture_username_userB(self):
        with self.assertRaises(BflaGuardrailError):
            assert_disposable_target("userB")

    def test_refuses_admin(self):
        with self.assertRaises(BflaGuardrailError):
            assert_disposable_target("admin")

    def test_refuses_name1(self):
        with self.assertRaises(BflaGuardrailError):
            assert_disposable_target("name1")

    def test_accepts_disposable_pattern(self):
        # Must not raise.
        assert_disposable_target("bfla_disposable_01")

    def test_accepts_disposable_pattern_large_number(self):
        assert_disposable_target("bfla_disposable_99")

    def test_accepts_bfla_run_pattern_victim(self):
        assert_disposable_target("bfla-a1b2c3d4-victim")

    def test_accepts_bfla_run_pattern_delete_control(self):
        assert_disposable_target("bfla-a1b2c3d4-delete-control")

    def test_accepts_bfla_run_pattern_actor(self):
        assert_disposable_target("bfla-a1b2c3d4-actor")

    def test_refuses_arbitrary_username(self):
        with self.assertRaises(BflaGuardrailError):
            assert_disposable_target("random_user")

    def test_refuses_empty_string(self):
        with self.assertRaises(BflaGuardrailError):
            assert_disposable_target("")

    def test_refuses_none(self):
        with self.assertRaises(BflaGuardrailError):
            assert_disposable_target(None)


class BuildFindingsTests(unittest.TestCase):
    """Findings artifact must reflect execution evidence accurately."""

    def test_denied_control_findings(self):
        receipt = {
            "outcome": "DENIED_CONTROL",
            "operations": {
                "unprivileged_delete": {"status": 401, "target_survived": True},
                "admin_delete_control": {"status": 200, "target_absent": True},
            },
        }
        manifest = {
            "destructive_targets": [
                {"username": "bfla-a1b2c3d4-victim"},
                {"username": "bfla-a1b2c3d4-delete-control"},
            ],
        }
        findings = _build_findings("a1b2c3d4", receipt, manifest)
        self.assertEqual(findings["overall_verdict"], "DENIED_CONTROL")
        self.assertEqual(findings["week"], 4)
        self.assertEqual(findings["finding_id"], "W4-BFLA-01")
        self.assertFalse(findings["credential_or_response_bodies_exported"])
        self.assertEqual(len(findings["cases"]), 2)
        self.assertEqual(findings["cases"][0]["verdict"], "DENIED")
        self.assertEqual(findings["cases"][0]["post_condition"], "user still exists")
        self.assertEqual(findings["cases"][1]["verdict"], "POSITIVE_CONTROL")
        self.assertEqual(findings["cases"][1]["post_condition"], "user absent")

    def test_confirmed_findings(self):
        receipt = {
            "outcome": "BFLA_CONFIRMED_DESTRUCTIVE",
            "operations": {
                "unprivileged_delete": {"status": 200, "target_survived": False},
                "admin_delete_control": {"status": None, "target_absent": None},
            },
        }
        manifest = {
            "destructive_targets": [
                {"username": "bfla-x1y2z3w4-victim"},
                {"username": "bfla-x1y2z3w4-delete-control"},
            ],
        }
        findings = _build_findings("x1y2z3w4", receipt, manifest)
        self.assertEqual(findings["overall_verdict"], "BFLA_CONFIRMED_DESTRUCTIVE")
        self.assertEqual(findings["cases"][0]["verdict"], "BFLA_CONFIRMED")
        self.assertEqual(findings["cases"][0]["post_condition"], "user absent")


class RunBflaWeek4Tests(unittest.TestCase):
    """Orchestrator must call guardrail before reading execution evidence."""

    def test_guardrail_called_for_each_target(self):
        """The guardrail must be called for every destructive target username."""
        checked_usernames = []
        original_assert = assert_disposable_target

        def tracking_assert(username):
            checked_usernames.append(username)
            original_assert(username)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            results = root / "results"
            bfla_results = root / "bfla-results"
            run_dir = bfla_results / "a1b2c3d4"
            run_dir.mkdir(parents=True)

            # Write a fake execution receipt.
            receipt = {
                "schema_version": 1,
                "workflow": "vampi-disposable-bfla-v1",
                "run_id": "a1b2c3d4",
                "outcome": "DENIED_CONTROL",
                "operations": {
                    "unprivileged_delete": {"status": 401, "target_survived": True},
                    "admin_delete_control": {"status": 200, "target_absent": True},
                },
                "credential_or_response_bodies_exported": False,
            }
            (run_dir / "execution-receipt.json").write_text(
                json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
            )

            # Write a fake manifest.
            from bfla_disposable.manifest import build_manifest

            manifest = build_manifest("a1b2c3d4")
            (run_dir / "destructive-target-manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

            with patch("week4.bfla_executor.assert_disposable_target", side_effect=tracking_assert):
                findings = run_bfla_week4(
                    "a1b2c3d4",
                    results_root=str(results),
                    bfla_results_root=str(bfla_results),
                )

        # Guardrail must have been called for both target usernames,
        # once for the built manifest and once for the loaded manifest.
        self.assertIn("bfla-a1b2c3d4-victim", checked_usernames)
        self.assertIn("bfla-a1b2c3d4-delete-control", checked_usernames)
        self.assertEqual(findings["overall_verdict"], "DENIED_CONTROL")

    def test_raises_when_receipt_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(BflaGuardrailError):
                run_bfla_week4(
                    "a1b2c3d4",
                    results_root=tmpdir,
                    bfla_results_root=tmpdir,
                )


if __name__ == "__main__":
    unittest.main()
