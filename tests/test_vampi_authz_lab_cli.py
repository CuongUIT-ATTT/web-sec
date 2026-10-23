import io
import unittest
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from vampi_authz_lab import cli
from week2.request_runner import SafetyError


class CliTests(unittest.TestCase):
    def test_check_inputs_reports_metadata_without_network(self):
        report = {"operation_count": 14, "fixture_count": 4, "role_names": ["admin", "userA", "userB"]}
        stdout = io.StringIO()
        with patch("vampi_authz_lab.cli.validate_inputs", return_value=report) as validate_inputs, patch(
            "vampi_authz_lab.cli.validate_base_url"
        ) as validate_base_url, redirect_stdout(stdout):
            status = cli.main(["check-inputs"])

        self.assertEqual(status, 0)
        validate_base_url.assert_called_once_with("http://127.0.0.1:5000")
        validate_inputs.assert_called_once()
        self.assertIn("Inputs valid: 14 operations, 4 fixtures, roles=admin,userA,userB", stdout.getvalue())

    def test_default_input_paths_use_current_working_directory(self):
        with patch("vampi_authz_lab.cli.validate_inputs", return_value={"operation_count": 0, "fixture_count": 0, "role_names": []}) as validate_inputs, patch(
            "vampi_authz_lab.cli.validate_base_url"
        ), patch("vampi_authz_lab.cli.PROJECT_ROOT", Path("/tmp/local-lab")), redirect_stdout(io.StringIO()):
            cli.main(["check-inputs"])

        supplied_paths = validate_inputs.call_args.args
        self.assertEqual(supplied_paths[0], Path("/tmp/local-lab/vampi_spec.json"))
        self.assertEqual(supplied_paths[1], Path("/tmp/local-lab/roles_config.json"))
        self.assertEqual(supplied_paths[2], Path("/tmp/local-lab/ownership.csv"))

    def test_checks_zap_manifest_without_network_dispatch(self):
        manifest = {"assessment_id": "local-safe-zap", "target": "http://127.0.0.1:5000"}
        stdout = io.StringIO()
        with patch("vampi_authz_lab.cli.load_zap_allowlist", return_value=manifest), patch(
            "vampi_authz_lab.cli.approved_request_pairs", return_value={("GET", "/books/v1/known-book")}
        ), patch("vampi_authz_lab.cli.validate_base_url") as validate_base_url, redirect_stdout(stdout):
            status = cli.main(["check-zap-allowlist"])

        self.assertEqual(status, 0)
        validate_base_url.assert_not_called()
        self.assertIn("no scan was started", stdout.getvalue())

    def test_rejects_unsafe_base_url_before_command_dispatch(self):
        stderr = io.StringIO()
        with patch("vampi_authz_lab.cli.validate_base_url", side_effect=SafetyError("local target only")), patch(
            "vampi_authz_lab.cli.validate_inputs"
        ) as validate_inputs, redirect_stderr(stderr):
            status = cli.main(["check-inputs", "--base-url", "http://example.test"])

        self.assertEqual(status, 2)
        validate_inputs.assert_not_called()
        self.assertIn("Command stopped safely: local target only", stderr.getvalue())

    def test_verify_does_not_rerun_pipeline(self):
        verification = {
            "verification": [
                {"outcome": "CONFIRMED_USER_TO_USER_BOLA"},
                {"outcome": "POLICY_DEPENDENT_ADMIN_ACCESS"},
            ]
        }
        stdout = io.StringIO()
        with patch("vampi_authz_lab.cli.run_verification", return_value=verification) as run_verification, patch(
            "vampi_authz_lab.cli.run_week3_workflow"
        ) as workflow, redirect_stdout(stdout):
            status = cli.main(["verify"])

        self.assertEqual(status, 0)
        run_verification.assert_called_once()
        workflow.assert_not_called()
        self.assertIn("1 user-to-user BOLA cases reproduced", stdout.getvalue())

    def test_week3_reports_measured_timing(self):
        workflow = {"timing": {"case_count": 12, "elapsed_ms": 1990.362}}
        stdout = io.StringIO()
        with patch("vampi_authz_lab.cli.run_week3_workflow", return_value=workflow), redirect_stdout(stdout):
            status = cli.main(["week3"])

        self.assertEqual(status, 0)
        self.assertIn("12 cases in 1990.362 ms", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
