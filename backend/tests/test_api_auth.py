import ipaddress

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app


def test_write_endpoints_require_authenticated_session_and_csrf(tmp_path) -> None:
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
        assert client.post("/api/projects", json={"name": "Unauthenticated"}).status_code == 401
        assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
        login = client.post("/api/auth/login", json={"password": "password"})
        assert client.post("/api/projects", json={"name": "Missing CSRF"}).status_code == 403
        csrf = login.json()["csrf_token"]
        assert client.post("/api/projects", json={"name": "Protected"}, headers={"X-CSRF-Token": csrf}).status_code == 201
