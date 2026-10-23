import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bfla_disposable.manifest import BflaManifestError, write_manifest
from bfla_disposable import preflight


class DisposableBflaPreflightTests(unittest.TestCase):
    run_id = "a1b2c3d4"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.results_root = self.root / "results"
        self.run_dir = self.root / ".bfla-runs" / self.run_id
        self.project = f"vampi-bfla-{self.run_id}"
        write_manifest(self.run_id, self.results_root)

    def test_preflight_writes_credential_free_attestation(self):
        def fake_run(command):
            if command[:3] == ["docker", "inspect", "vampi-week1"]:
                return subprocess.CompletedProcess(command, 0, "shared-id running\n", "")
            if command[:4] == ["docker", "image", "inspect", "vampi-week1:local"]:
                return subprocess.CompletedProcess(command, 0, "sha256:lab-image\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("bfla_disposable.preflight._assert_port_available"), patch(
            "bfla_disposable.preflight._run", side_effect=fake_run
        ):
            receipt = preflight.preflight(self.run_id, self.project, self.run_dir, self.results_root)

        persisted = json.loads((self.results_root / self.run_id / "preflight-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "PREFLIGHT_COMPLETE")
        self.assertEqual(persisted["shared_week1_before"], {"id": "shared-id", "state": "running"})
        self.assertFalse(persisted["credential_or_response_bodies_exported"])
        self.assertNotIn("token", json.dumps(persisted).lower())

    def test_preflight_rejects_nonempty_run_directory(self):
        self.run_dir.mkdir(parents=True, mode=0o700)
        (self.run_dir / "unexpected").write_text("not a secret", encoding="utf-8")

        with self.assertRaises(BflaManifestError):
            preflight.preflight(self.run_id, self.project, self.run_dir, self.results_root)

    def test_receipt_must_bind_to_exact_run_and_project(self):
        path = self.results_root / self.run_id / "preflight-receipt.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "workflow": "vampi-disposable-bfla-v1",
                    "run_id": self.run_id,
                    "target": "http://127.0.0.1:5003",
                    "compose_project": self.project,
                    "shared_week1_before": {"id": "shared-id", "state": "running"},
                    "disposable_image_id": "sha256:lab-image",
                    "port_5003_available_before_compose": True,
                    "existing_project_objects": {"containers": [], "volumes": []},
                    "credential_or_response_bodies_exported": False,
                    "status": "PREFLIGHT_COMPLETE",
                }
            ),
            encoding="utf-8",
        )

        loaded = preflight.load_preflight_receipt(self.run_id, self.project, self.results_root)
        self.assertEqual(loaded["run_id"], self.run_id)
        with self.assertRaises(BflaManifestError):
            preflight.load_preflight_receipt(self.run_id, "vampi-bfla-other123", self.results_root)


if __name__ == "__main__":
    unittest.main()
