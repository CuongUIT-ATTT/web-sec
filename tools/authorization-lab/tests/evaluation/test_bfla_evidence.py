"""Tests for authz_lab.evaluation.bfla_evidence guardrail and findings builder."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authz_lab.evaluation.bfla_evidence import (
    BflaGuardrailError,
    assert_disposable_target,
    run_bfla_evaluation,
    _build_findings,
)


_NETWORK_PATCH = patch("socket.socket.connect", side_effect=AssertionError("network blocked"))
_PROCESS_PATCH = patch("subprocess.run", side_effect=AssertionError("process blocked"))


def setUpModule():
    _NETWORK_PATCH.start()
    _PROCESS_PATCH.start()


def tearDownModule():
    _PROCESS_PATCH.stop()
    _NETWORK_PATCH.stop()


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
        self.assertEqual(findings["overall_verdict"], "INCONCLUSIVE")
        self.assertEqual(findings["week"], 4)
        self.assertEqual(findings["finding_id"], "W4-BFLA-01")
        self.assertFalse(findings["credential_or_response_bodies_exported"])
        self.assertEqual(len(findings["cases"]), 2)
        self.assertEqual(findings["cases"][0]["verdict"], "INCONCLUSIVE")
        self.assertEqual(findings["cases"][0]["post_condition"], "unknown")
        self.assertEqual(findings["cases"][1]["verdict"], "INCONCLUSIVE")
        self.assertEqual(findings["cases"][1]["post_condition"], "unknown")

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
        self.assertEqual(findings["overall_verdict"], "INCONCLUSIVE")
        self.assertEqual(findings["cases"][0]["verdict"], "INCONCLUSIVE")
        self.assertEqual(findings["cases"][0]["post_condition"], "unknown")


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.socket.connect", side_effect=AssertionError("network blocked"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.process = patch("subprocess.run", side_effect=AssertionError("process blocked"))
        self.process.start()
        self.addCleanup(self.process.stop)

    def fixture(self, denied=False):
        run = "a1b2c3d4"
        from authz_lab.disposable.manifest import build_manifest
        manifest = build_manifest(run)
        def operation(index, admin, exists):
            target = manifest["destructive_targets"][index]
            return {"status": 200 if admin or not exists else 401,
                    "target_absent" if admin else "target_survived": not exists if admin else exists,
                    "proof": {
                        "baseline": {"status": 200, "username": target["username"], "fresh": True},
                        "principal": {"status": 200, "username": "admin" if admin else f"bfla-{run}-actor", "admin": admin},
                        "postcondition": {"status": 200 if exists else 404, "username": target["username"], "path": target["path"]}}}
        receipt = {"schema_version": 1, "run_id": run, "workflow": "vampi-disposable-bfla-v1",
                   "target": "http://127.0.0.1:5003", "outcome": "DENIED_CONTROL" if denied else "BFLA_CONFIRMED_DESTRUCTIVE",
                   "operations": {"unprivileged_delete": operation(0, False, denied)}}
        if denied:
            receipt["operations"]["admin_delete_control"] = operation(1, True, False)
        return run, receipt, manifest

    def test_positive_and_denied_proof(self):
        for denied in (False, True):
            with self.subTest(denied=denied):
                run, receipt, manifest = self.fixture(denied)
                findings = _build_findings(run, receipt, manifest)
                self.assertEqual(findings["overall_verdict"], receipt["outcome"])
                self.assertEqual(findings["cases"][0]["verdict"], "DENIED" if denied else "BFLA_CONFIRMED")

    def test_unknown_malformed_and_survivor_never_confirm(self):
        for value in (None, True, 0, 1, "false", [], {}, "missing"):
            with self.subTest(value=value):
                run, receipt, manifest = self.fixture()
                op = receipt["operations"]["unprivileged_delete"]
                if value == "missing":
                    del op["target_survived"]
                else:
                    op["target_survived"] = value
                self.assertEqual(_build_findings(run, receipt, manifest)["overall_verdict"], "INCONCLUSIVE")

    def test_invalid_or_contradictory_proof(self):
        mutations = [
            lambda r, o: r.update(run_id="other"),
            lambda r, o: r.update(workflow="other"),
            lambda r, o: r.update(schema_version=True),
            lambda r, o: r.update(outcome="DENIED_CONTROL"),
            lambda r, o: o.pop("proof"),
            lambda r, o: o["proof"]["baseline"].update(fresh=False),
            lambda r, o: o["proof"]["baseline"].update(username="other"),
            lambda r, o: o["proof"]["principal"].update(admin=True),
            lambda r, o: o["proof"]["principal"].update(username="other"),
            lambda r, o: o["proof"]["postcondition"].update(status=500),
            lambda r, o: o["proof"]["postcondition"].update(status=401),
            lambda r, o: o["proof"]["postcondition"].update(status=200),
            lambda r, o: o["proof"].update(postcondition=None),
            lambda r, o: r.update(operations=[]),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                run, receipt, manifest = self.fixture()
                mutate(receipt, receipt["operations"]["unprivileged_delete"])
                findings = _build_findings(run, receipt, manifest)
                self.assertEqual(findings["overall_verdict"], "INCONCLUSIVE")
                self.assertEqual(findings["cases"][0]["verdict"], "INCONCLUSIVE")


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
            from authz_lab.disposable.manifest import build_manifest

            manifest = build_manifest("a1b2c3d4")
            (run_dir / "destructive-target-manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )

            with patch("authz_lab.evaluation.bfla_evidence.assert_disposable_target", side_effect=tracking_assert):
                findings = run_bfla_evaluation(
                    "a1b2c3d4",
                    results_root=str(results),
                    bfla_results_root=str(bfla_results),
                )

        # Guardrail must have been called for both target usernames,
        # once for the built manifest and once for the loaded manifest.
        self.assertIn("bfla-a1b2c3d4-victim", checked_usernames)
        self.assertIn("bfla-a1b2c3d4-delete-control", checked_usernames)
        self.assertEqual(findings["overall_verdict"], "INCONCLUSIVE")

    def test_raises_when_receipt_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(BflaGuardrailError):
                run_bfla_evaluation(
                    "a1b2c3d4",
                    results_root=tmpdir,
                    bfla_results_root=tmpdir,
                )


if __name__ == "__main__":
    unittest.main()
