from pathlib import Path
import ipaddress

from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app


def test_app_exposes_namespaced_health_and_contract(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "app.sqlite3",
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key="unused",
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32768,
        default_timeout_seconds=5.0,
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        contract = client.get("/api/openapi.json").json()

    assert "/api/health" in contract["paths"]
    assert "/api/projects" in contract["paths"]
