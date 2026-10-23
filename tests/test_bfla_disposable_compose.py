import unittest
from pathlib import Path


class DisposableBflaComposeTests(unittest.TestCase):
    def test_compose_has_isolated_loopback_only_shape(self):
        text = (Path(__file__).resolve().parent.parent / "bfla-disposable" / "compose.yaml").read_text(encoding="utf-8")

        self.assertIn('"127.0.0.1:5003:5000"', text)
        self.assertIn("vampi_db:/vampi/database", text)
        self.assertIn("internal: true", text)
        self.assertIn("host_access:", text)
        self.assertIn("project.vampi_authz_lab.workflow", text)
        self.assertIn("no-new-privileges:true", text)
        self.assertNotIn("container_name:", text)
        self.assertNotIn("../VAmPI-source:/", text)
        self.assertNotIn("5000:5000", text)


if __name__ == "__main__":
    unittest.main()
