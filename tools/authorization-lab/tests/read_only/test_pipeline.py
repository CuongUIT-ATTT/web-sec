import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from authz_lab.read_only import pipeline


class PipelineTests(unittest.TestCase):
    def test_verification_writes_evidence_without_running_matrix(self):
        endpoints = [{"path": "/books/v1/{book_title}", "method": "GET"}]
        fixtures = [{"resource_type": "book", "resource_id": "known-book", "owner_role": "userA"}]
        roles = {"userA": {"username": "userA", "token": "Bearer " + "local-token-value"}}
        verification = [{"outcome": "CONFIRMED_USER_TO_USER_BOLA"}]
        findings = [{"id": "W3-01", "status": "CONFIRMED"}]

        with tempfile.TemporaryDirectory() as temporary_directory, patch(
            "authz_lab.read_only.pipeline.validate_base_url"
        ) as validate_base_url, patch("authz_lab.read_only.pipeline.load_spec", return_value={}), patch(
            "authz_lab.read_only.pipeline.extract_endpoints", return_value=endpoints
        ), patch("authz_lab.read_only.pipeline.load_roles_config", return_value=roles), patch(
            "authz_lab.read_only.pipeline.load_ownership", return_value=fixtures
        ), patch(
            "authz_lab.read_only.pipeline.independently_verify_books", return_value=verification
        ) as independently_verify_books, patch(
            "authz_lab.read_only.pipeline.classify_findings", return_value=findings
        ), patch("authz_lab.read_only.pipeline.run_pipeline") as run_pipeline:
            output_dir = Path(temporary_directory) / "results"
            report = pipeline.run_verification(Path("spec.json"), Path("roles.json"), Path("ownership.csv"), output_dir)

            self.assertTrue((output_dir / "manual_verification.json").exists())
            self.assertTrue((output_dir / "independent_verification_findings.json").exists())

        validate_base_url.assert_called_once_with("http://127.0.0.1:5000")
        independently_verify_books.assert_called_once_with(roles, fixtures, "http://127.0.0.1:5000")
        run_pipeline.assert_not_called()
        self.assertEqual(report["findings"], findings)


if __name__ == "__main__":
    unittest.main()
