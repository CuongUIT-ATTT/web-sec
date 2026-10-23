import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bfla_disposable import teardown


class DisposableBflaTeardownTests(unittest.TestCase):
    run_id = "a1b2c3d4"

    def test_teardown_uses_only_project_scoped_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / ".bfla-runs" / self.run_id
            run_dir.mkdir(mode=0o700, parents=True)
            compose = Path(__file__).resolve().parent.parent / "bfla-disposable" / "compose.yaml"
            commands = []

            def fake_run(command):
                commands.append(command)
                if command[:3] == ["docker", "inspect", "vampi-week1"]:
                    return subprocess.CompletedProcess(command, 0, "shared-id running\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            preflight_receipt = {"shared_week1_before": {"id": "shared-id", "state": "running"}}
            with patch("bfla_disposable.teardown._run", side_effect=fake_run), patch(
                "bfla_disposable.teardown.load_preflight_receipt", return_value=preflight_receipt
            ):
                receipt = teardown.teardown(
                    self.run_id,
                    f"vampi-bfla-{self.run_id}",
                    run_dir,
                    compose,
                    root / "results",
                )

        flattened = "\n".join(" ".join(command) for command in commands)
        self.assertEqual(receipt["status"], "TEARDOWN_COMPLETE")
        self.assertIn("docker compose --project-name vampi-bfla-a1b2c3d4", flattened)
        self.assertNotIn("docker rm", flattened)
        self.assertNotIn("docker stop", flattened)
        self.assertNotIn("docker system prune", flattened)
        self.assertNotIn("docker rm", flattened)
        self.assertEqual(sum(command[:3] == ["docker", "inspect", "vampi-week1"] for command in commands), 2)
        self.assertEqual(receipt["shared_week1_preflight"], {"id": "shared-id", "state": "running"})
        self.assertTrue(receipt["preflight_receipt_available"])


if __name__ == "__main__":
    unittest.main()
