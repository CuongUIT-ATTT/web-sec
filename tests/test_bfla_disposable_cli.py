import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from bfla_disposable import cli


class DisposableBflaCliTests(unittest.TestCase):
    def test_preflight_dispatches_without_compose_or_http(self):
        receipt = {"status": "PREFLIGHT_COMPLETE"}
        stdout = io.StringIO()
        with patch("bfla_disposable.cli.preflight", return_value=receipt) as preflight, redirect_stdout(stdout):
            status = cli.main(["preflight", "--run-id", "a1b2c3d4"])

        self.assertEqual(status, 0)
        preflight.assert_called_once()
        self.assertIn("PREFLIGHT_COMPLETE", stdout.getvalue())

    def test_preflight_stops_safely_on_attestation_failure(self):
        stderr = io.StringIO()
        with patch("bfla_disposable.cli.preflight", side_effect=ValueError("shared lab differs")), redirect_stderr(stderr):
            status = cli.main(["preflight", "--run-id", "a1b2c3d4"])

        self.assertEqual(status, 2)
        self.assertIn("Command stopped safely: shared lab differs", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
