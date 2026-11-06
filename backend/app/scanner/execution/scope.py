"""Fail-closed target validation for explicit IPv4/IPv6 lab ranges."""

from __future__ import annotations

import ipaddress
from urllib.parse import unquote, urlsplit

from backend.app.core.settings import Settings


class TargetScopeError(ValueError):
    """Raised before a request escapes the declared lab scope."""


def _validate_path(path: str) -> None:
    if any(unquote(segment) in {".", ".."} for segment in path.split("/")):
        raise TargetScopeError("URL không được chứa phân đoạn điều hướng path.")


def validate_base_url(base_url: str, settings: Settings) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise TargetScopeError("Chỉ hỗ trợ URL HTTP hoặc HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise TargetScopeError("URL đích không được chứa userinfo, query hoặc fragment.")
    _validate_path(parsed.path)
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as error:
        raise TargetScopeError("MVP chỉ hỗ trợ địa chỉ IP lab, không hỗ trợ hostname/DNS.") from error
    if not any(address in network for network in settings.target_networks):
        raise TargetScopeError("IP đích không thuộc phạm vi lab được cho phép.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as error:
        raise TargetScopeError("Cổng đích không hợp lệ.") from error
    if port not in settings.allowed_ports:
        raise TargetScopeError("Cổng đích không thuộc phạm vi được cho phép.")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def build_request_url(base_url: str, api_path: str, settings: Settings) -> str:
    safe_base = validate_base_url(base_url, settings)
    parsed = urlsplit(api_path)
    if not api_path.startswith("/") or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise TargetScopeError("Operation phải là path tuyệt đối không có query hoặc fragment.")
    _validate_path(parsed.path)
    if api_path == "/createdb" or api_path.startswith("/createdb/"):
        raise TargetScopeError("Endpoint khởi tạo lại dữ liệu bị cấm vĩnh viễn.")
    base = urlsplit(safe_base)
    prefix = base.path.rstrip("/")
    request_path = f"{prefix}{api_path}" if prefix else api_path
    return f"{base.scheme}://{base.netloc}{request_path}"
