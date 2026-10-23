import json
import tempfile
import unittest
from pathlib import Path

from bfla_disposable.manifest import (
    ALLOWED_BASE_URL,
    BflaManifestError,
    build_manifest,
    expected_project_name,
    load_manifest,
    validate_base_url,
    validate_manifest,
    validate_run_directory,
    validate_run_id,
    write_manifest,
)


class DisposableBflaManifestTests(unittest.TestCase):
    run_id = "a1b2c3d4"

    def test_builds_exact_disposable_target_scope(self):
        manifest = validate_manifest(build_manifest(self.run_id))

        self.assertEqual(manifest["target"]["base_url"], ALLOWED_BASE_URL)
        self.assertEqual(manifest["target"]["compose_project"], expected_project_name(self.run_id))
        self.assertEqual([item["method"] for item in manifest["destructive_targets"]], ["DELETE", "DELETE"])
        self.assertNotIn("auth_token", json.dumps(manifest))
        self.assertNotIn("Bearer ", json.dumps(manifest))

    def test_rejects_unsafe_run_target_and_project(self):
        for run_id in ("short", "UPPERCASE1", "safe-id-01", "a" * 33):
            with self.subTest(run_id=run_id):
                with self.assertRaises(BflaManifestError):
                    validate_run_id(run_id)
        for target in (
            "http://127.0.0.1:5000",
            "http://localhost:5003",
            "https://127.0.0.1:5003",
            "http://127.0.0.1:5003/path",
            "http://127.0.0.1:5003?x=1",
        ):
            with self.subTest(target=target):
                with self.assertRaises(BflaManifestError):
                    validate_base_url(target)

    def test_rejects_symlinked_or_wrong_run_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            valid = root / ".bfla-runs" / self.run_id
            self.assertEqual(validate_run_directory(valid, self.run_id), valid)
            wrong_parent = root / "other" / self.run_id
            with self.assertRaises(BflaManifestError):
                validate_run_directory(wrong_parent, self.run_id)
            valid.parent.mkdir(parents=True)
            target = root / ".bfla-runs" / "targetdir"
            target.mkdir()
            linked = root / ".bfla-runs" / "b1c2d3e4"
            linked.symlink_to(target, target_is_directory=True)
            with self.assertRaises(BflaManifestError):
                validate_run_directory(linked, "b1c2d3e4")

    def test_rejects_manifest_mutation(self):
        manifest = build_manifest(self.run_id)
        manifest["destructive_targets"][0]["path"] = "/users/v1/another-user"
        with self.assertRaises(BflaManifestError):
            validate_manifest(manifest)

    def test_writes_and_loads_non_secret_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory) / "results"
            path = write_manifest(self.run_id, output_root)
            loaded = load_manifest(path)
            contents = path.read_text(encoding="utf-8")

        self.assertEqual(loaded["run_id"], self.run_id)
        self.assertNotIn("auth_token", contents)


if __name__ == "__main__":
    unittest.main()
