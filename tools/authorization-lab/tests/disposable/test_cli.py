import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from authz_lab.disposable import cli


class DisposableBflaCliTests(unittest.TestCase):
    def test_execution_requires_explicit_approval_inputs(self):
        for stage in ("execute", "execute-extended"):
            with self.subTest(stage=stage), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.build_parser().parse_args([stage, "--run-id", "a1b2c3d4"])
                self.assertEqual(error.exception.code, 2)

    def test_execution_passes_operator_inputs_without_creating_approval(self):
        from pathlib import Path
        for stage, target, result in (("execute", "execute", {"outcome": "DENIED_CONTROL"}),
                                       ("execute-extended", "execute_extended", {"run_id": "a1b2c3d4"})):
            with self.subTest(stage=stage), patch.object(cli, target, return_value=result) as operation, redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main([stage, "--run-id", "a1b2c3d4", "--approval", "/synthetic/approval.json", "--approval-digest", "a" * 64]), 0)
                self.assertEqual(operation.call_args.kwargs, {"approval": Path("/synthetic/approval.json"), "approval_digest": "a" * 64})

    def test_preflight_dispatches_without_compose_or_http(self):
        receipt = {"status": "PREFLIGHT_COMPLETE"}
        stdout = io.StringIO()
        with patch("authz_lab.disposable.cli.preflight", return_value=receipt) as preflight, redirect_stdout(stdout):
            status = cli.main(["preflight", "--run-id", "a1b2c3d4"])

        self.assertEqual(status, 0)
        preflight.assert_called_once()
        self.assertIn("PREFLIGHT_COMPLETE", stdout.getvalue())

    def test_preflight_stops_safely_on_attestation_failure(self):
        stderr = io.StringIO()
        with patch("authz_lab.disposable.cli.preflight", side_effect=ValueError("shared lab differs")), redirect_stderr(stderr):
            status = cli.main(["preflight", "--run-id", "a1b2c3d4"])

        self.assertEqual(status, 2)
        self.assertIn("Command stopped safely: shared lab differs", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
