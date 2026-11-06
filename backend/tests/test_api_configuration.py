from pathlib import Path
import ipaddress

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app


def test_configuration_api_persists_scoped_target_and_write_only_identity(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "app.sqlite3",
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key=Fernet.generate_key().decode("ascii"),
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32768,
        default_timeout_seconds=5.0,
    )
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/projects", json={"name": "Lab", "description": "Local test"}).status_code == 401
        login = client.post("/api/auth/login", json={"password": "password"})
        csrf_headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        project = client.post("/api/projects", json={"name": "Lab", "description": "Local test"}, headers=csrf_headers).json()
        target_response = client.post(f"/api/projects/{project['id']}/targets", json={"base_url": "http://127.0.0.1:5000/api"}, headers=csrf_headers)
        identity_response = client.post(
            f"/api/projects/{project['id']}/identities",
            json={
                "display_name": "Alice",
                "role": "reader",
                "principal_pointer": "/data/username",
                "expected_principal": "alice",
                "bearer_token": "super-secret-token",
            },
            headers=csrf_headers,
        )
        identities = client.get(f"/api/projects/{project['id']}/identities").json()

    assert login.status_code == 200
    assert target_response.status_code == 201
    assert identity_response.status_code == 201
    assert identity_response.json()["has_secret"] is True
    assert "bearer_token" not in identity_response.text
    assert "super-secret-token" not in identity_response.text
    assert identities[0]["display_name"] == "Alice"
    assert "super-secret-token" not in str(identities)
