import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vampi_authz_lab import pipeline


class PipelineTests(unittest.TestCase):
    def test_verification_writes_evidence_without_running_matrix(self):
        endpoints = [{"path": "/books/v1/{book_title}", "method": "GET"}]
        fixtures = [{"resource_type": "book", "resource_id": "known-book", "owner_role": "userA"}]
        roles = {"userA": {"username": "userA", "token": "Bearer " + "local-token-value"}}
        verification = [{"outcome": "CONFIRMED_USER_TO_USER_BOLA"}]
        findings = [{"id": "W3-01", "status": "CONFIRMED"}]

        with tempfile.TemporaryDirectory() as temporary_directory, patch(
            "vampi_authz_lab.pipeline.validate_base_url"
        ) as validate_base_url, patch("vampi_authz_lab.pipeline.load_spec", return_value={}), patch(
            "vampi_authz_lab.pipeline.extract_endpoints", return_value=endpoints
        ), patch("vampi_authz_lab.pipeline.load_roles_config", return_value=roles), patch(
            "vampi_authz_lab.pipeline.load_ownership", return_value=fixtures
        ), patch(
            "vampi_authz_lab.pipeline.independently_verify_books", return_value=verification
        ) as independently_verify_books, patch(
            "vampi_authz_lab.pipeline.classify_findings", return_value=findings
        ), patch("vampi_authz_lab.pipeline.run_pipeline") as run_pipeline:
            output_dir = Path(temporary_directory) / "results"
            report = pipeline.run_verification(Path("spec.json"), Path("roles.json"), Path("ownership.csv"), output_dir)

            self.assertTrue((output_dir / "week3_manual_verification.json").exists())
            self.assertTrue((output_dir / "week3_findings.json").exists())

        validate_base_url.assert_called_once_with("http://127.0.0.1:5000")
        independently_verify_books.assert_called_once_with(roles, fixtures, "http://127.0.0.1:5000")
        run_pipeline.assert_not_called()
        self.assertEqual(report["findings"], findings)


if __name__ == "__main__":
    unittest.main()
