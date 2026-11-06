import ipaddress
from pathlib import Path

import pytest

from backend.app.core.settings import Settings
from backend.app.scanner.execution.scope import TargetScopeError, build_request_url, validate_base_url


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_path=Path("test.sqlite3"),
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key="unused",
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32768,
        default_timeout_seconds=5.0,
    )


def test_scope_accepts_explicit_lab_ip_port_and_prefix(settings: Settings) -> None:
    assert validate_base_url("http://127.0.0.1:5000/api", settings) == "http://127.0.0.1:5000/api"
    assert build_request_url("http://127.0.0.1:5000/api", "/books/a", settings) == "http://127.0.0.1:5000/api/books/a"


@pytest.mark.parametrize("url", ["http://localhost:5000", "http://127.0.0.2:5000", "http://127.0.0.1:80", "http://127.0.0.1:5000?next=x"])
def test_scope_rejects_hostnames_and_out_of_scope_target(url: str, settings: Settings) -> None:
    with pytest.raises(TargetScopeError):
        validate_base_url(url, settings)


@pytest.mark.parametrize("path", ["/createdb", "/createdb/reset", "https://127.0.0.1:5000/api/books", "/../outside", "/%2e%2e/outside"])
def test_scope_rejects_forbidden_or_escape_paths(path: str, settings: Settings) -> None:
    with pytest.raises(TargetScopeError):
        build_request_url("http://127.0.0.1:5000/api", path, settings)
