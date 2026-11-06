import os

import pytest
from cryptography.fernet import Fernet

from backend.app.core.settings import Settings, SettingsError


def test_settings_fail_closed_without_session_secret(monkeypatch) -> None:
    monkeypatch.setenv("AUTHZ_ADMIN_PASSWORD", "password")
    monkeypatch.setenv("AUTHZ_SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("AUTHZ_ALLOWED_TARGET_NETWORKS", "127.0.0.1/32")
    monkeypatch.delenv("AUTHZ_SESSION_SECRET", raising=False)

    with pytest.raises(SettingsError):
        Settings.from_environment()


def test_settings_load_explicit_scope(monkeypatch) -> None:
    monkeypatch.setenv("AUTHZ_ADMIN_PASSWORD", "password")
    monkeypatch.setenv("AUTHZ_SESSION_SECRET", "a" * 32)
    monkeypatch.setenv("AUTHZ_SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("AUTHZ_ALLOWED_TARGET_NETWORKS", "127.0.0.1/32")
    monkeypatch.setenv("AUTHZ_ALLOWED_TARGET_PORTS", "5000")

    settings = Settings.from_environment()

    assert settings.allowed_ports == frozenset({5000})
    assert str(settings.target_networks[0]) == "127.0.0.1/32"
