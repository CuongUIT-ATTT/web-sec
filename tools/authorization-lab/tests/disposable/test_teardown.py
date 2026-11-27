import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authz_lab.disposable import teardown


class DisposableBflaTeardownTests(unittest.TestCase):
    run_id = "a1b2c3d4"

    def test_teardown_uses_only_project_scoped_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / ".bfla-runs" / self.run_id
            run_dir.mkdir(mode=0o700, parents=True)
            compose = Path(__file__).resolve().parents[4] / "deploy" / "labs" / "vampi-bfla-disposable.compose.yaml"
            (root / "results" / self.run_id).mkdir(parents=True)
            commands = []

            def fake_run(command):
                commands.append(command)
                if command[:3] == ["docker", "inspect", "vampi-week1"]:
                    return subprocess.CompletedProcess(command, 0, "shared-id running\n", "")
                return subprocess.CompletedProcess(command, 0, "", "")

            preflight_receipt = {"disposable_image_id": "image", "shared_week1_before": {"id": "shared-id", "state": "running"}}
            with patch("authz_lab.disposable.teardown._assert_disposable_runtime"), patch("authz_lab.disposable.teardown._run", side_effect=fake_run), patch(
                "authz_lab.disposable.teardown.load_preflight_receipt", return_value=preflight_receipt
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

class CleanupFailureTests(unittest.TestCase):
    def test_failed_down_retains_private_data_and_receipt(self):
        import json
        from authz_lab.disposable.preflight import compose_path
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / '.bfla-runs/a1b2c3d4'
            directory.mkdir(parents=True)
            evidence = root / 'results/a1b2c3d4'
            evidence.mkdir(parents=True)
            canary = directory / 'do-not-remove'
            canary.write_text('fixture')
            before = {'id': 'shared', 'state': 'running'}
            with patch.object(teardown, 'load_preflight_receipt', return_value={'shared_week1_before': before, 'disposable_image_id': 'image'}), patch.object(teardown, '_assert_disposable_runtime'), patch.object(teardown, '_week1_snapshot', return_value=before), patch.object(teardown, '_project_containers', return_value=[]), patch.object(teardown, '_project_volumes', return_value=[]), patch.object(teardown, '_run', return_value=subprocess.CompletedProcess([], 1, 'SECRET', 'SECRET')):
                with self.assertRaises(teardown.BflaExecutionError):
                    teardown.teardown('a1b2c3d4', 'vampi-bfla-a1b2c3d4', directory, compose_path(), root / 'results')
            self.assertTrue(canary.exists())
            receipt = (evidence / 'teardown-receipt.json').read_text()
            self.assertNotIn('SECRET', receipt)
            self.assertEqual(json.loads(receipt)['upstream_database_proof'], 'UNKNOWN')

    def test_arbitrary_compose_path_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'labs/vampi-bfla-disposable.compose.yaml'
            path.parent.mkdir()
            path.write_text('fixture')
            with self.assertRaises(ValueError):
                teardown._assert_compose_file(path)

class CleanupGateTests(unittest.TestCase):
    def test_bad_runtime_stops_before_down(self):
        from authz_lab.disposable.preflight import compose_path
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / '.bfla-runs/a1b2c3d4'
            run.mkdir(parents=True)
            with patch.object(teardown, 'load_preflight_receipt', return_value={'disposable_image_id': 'image'}), patch.object(teardown, '_assert_disposable_runtime', side_effect=RuntimeError('mismatch')), patch.object(teardown, '_run') as transport:
                with self.assertRaises(RuntimeError):
                    teardown.teardown('a1b2c3d4', 'vampi-bfla-a1b2c3d4', run, compose_path(), root / 'results')
                transport.assert_not_called()
            self.assertTrue(run.exists())
