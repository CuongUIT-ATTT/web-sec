import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bfla_disposable.manifest import BflaManifestError, write_manifest
from bfla_disposable import runner


class DisposableBflaRunnerTests(unittest.TestCase):
    run_id = "a1b2c3d4"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.results_root = self.root / "results"
        self.run_dir = self.root / ".bfla-runs" / self.run_id
        self.project = f"vampi-bfla-{self.run_id}"
        write_manifest(self.run_id, self.results_root)

    def test_rejects_out_of_scope_request(self):
        with self.assertRaises(BflaManifestError):
            runner._assert_request_scope("/books/v1/anything", "GET", None)
        with self.assertRaises(BflaManifestError):
            runner._assert_request_scope("/users/v1/anything", "PUT", None)

    def test_execute_records_denied_control_without_secrets(self):
        self.run_dir.mkdir(parents=True, mode=0o700)
        runner._write_secret(
            self.run_dir,
            {"run_id": self.run_id, "actor": {"token": "actor-token"}, "admin": {"token": "admin-token"}},
        )
        responses = iter([(401, None), (200, None), (200, None), (404, None)])
        preflight_receipt = {"disposable_image_id": "sha256:lab-image"}
        with patch("bfla_disposable.runner._load_attested_preflight", return_value=(preflight_receipt, {})), patch(
            "bfla_disposable.runner._assert_disposable_runtime"
        ), patch("bfla_disposable.runner._request", side_effect=lambda *args, **kwargs: next(responses)):
            result = runner.execute(self.run_id, self.project, self.run_dir, self.results_root)

        artifact = json.loads((self.results_root / self.run_id / "execution-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(result["outcome"], "DENIED_CONTROL")
        self.assertFalse(runner.artifact_has_secret_keys(artifact))
        self.assertNotIn("actor-token", json.dumps(artifact))

    def test_unprivileged_success_stops_before_admin_control(self):
        self.run_dir.mkdir(parents=True, mode=0o700)
        runner._write_secret(
            self.run_dir,
            {"run_id": self.run_id, "actor": {"token": "actor-token"}, "admin": {"token": "admin-token"}},
        )
        responses = iter([(200, None), (404, None)])
        preflight_receipt = {"disposable_image_id": "sha256:lab-image"}
        with patch("bfla_disposable.runner._load_attested_preflight", return_value=(preflight_receipt, {})), patch(
            "bfla_disposable.runner._assert_disposable_runtime"
        ), patch("bfla_disposable.runner._request", side_effect=lambda *args, **kwargs: next(responses)) as request:
            result = runner.execute(self.run_id, self.project, self.run_dir, self.results_root)

        self.assertEqual(result["outcome"], "BFLA_CONFIRMED_DESTRUCTIVE")
        self.assertEqual(request.call_count, 2)


if __name__ == "__main__":
    unittest.main()
