"""Environment-driven, fail-closed configuration for the single-process MVP."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path


class SettingsError(ValueError):
    """Raised when deployment settings would weaken the controlled MVP."""


@dataclass(frozen=True)
class Settings:
    database_path: Path
    admin_password: str
    session_secret: str
    secret_encryption_key: str
    target_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    allowed_ports: frozenset[int]
    max_response_bytes: int
    default_timeout_seconds: float
    secure_cookies: bool = False

    @classmethod
    def from_environment(cls) -> "Settings":
        database_path = Path(os.environ.get("AUTHZ_DATABASE_PATH", "data/authz-web.sqlite3"))
        admin_password = os.environ.get("AUTHZ_ADMIN_PASSWORD", "")
        session_secret = os.environ.get("AUTHZ_SESSION_SECRET", "")
        encryption_key = os.environ.get("AUTHZ_SECRET_ENCRYPTION_KEY", "")
        networks_text = os.environ.get("AUTHZ_ALLOWED_TARGET_NETWORKS", "")
        ports_text = os.environ.get("AUTHZ_ALLOWED_TARGET_PORTS", "80,443,5000")
        if not admin_password:
            raise SettingsError("AUTHZ_ADMIN_PASSWORD must be configured.")
        if len(session_secret) < 32:
            raise SettingsError("AUTHZ_SESSION_SECRET phải có ít nhất 32 ký tự.")
        if not encryption_key:
            raise SettingsError("AUTHZ_SECRET_ENCRYPTION_KEY must be configured.")
        if not networks_text:
            raise SettingsError("AUTHZ_ALLOWED_TARGET_NETWORKS must list explicit lab IP/CIDR ranges.")
        try:
            networks = tuple(ipaddress.ip_network(value.strip(), strict=False) for value in networks_text.split(",") if value.strip())
            ports = frozenset(int(value.strip()) for value in ports_text.split(",") if value.strip())
        except ValueError as error:
            raise SettingsError("Target network or port configuration is invalid.") from error
        if not networks or not ports or any(port < 1 or port > 65535 for port in ports):
            raise SettingsError("At least one valid target network and port are required.")
        return cls(
            database_path=database_path,
            admin_password=admin_password,
            session_secret=session_secret,
            secret_encryption_key=encryption_key,
            target_networks=networks,
            allowed_ports=ports,
            max_response_bytes=int(os.environ.get("AUTHZ_MAX_RESPONSE_BYTES", "32768")),
            default_timeout_seconds=float(os.environ.get("AUTHZ_DEFAULT_TIMEOUT_SECONDS", "5")),
            secure_cookies=os.environ.get("AUTHZ_SECURE_COOKIES", "false").lower() == "true",
        )
