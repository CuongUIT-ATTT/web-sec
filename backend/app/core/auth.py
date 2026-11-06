"""Single-admin session and CSRF guards for the loopback-first web application."""

from __future__ import annotations

import hmac
import secrets

from fastapi import HTTPException, Request, status

from backend.app.core.settings import Settings


def establish_admin_session(request: Request) -> str:
    """Rotate session state after password verification and return the CSRF value once."""
    csrf_token = secrets.token_urlsafe(32)
    request.session.clear()
    request.session["admin_authenticated"] = True
    request.session["csrf_token"] = csrf_token
    return csrf_token


def verify_admin_password(candidate: str, settings: Settings) -> bool:
    return hmac.compare_digest(candidate, settings.admin_password)


def require_admin(request: Request) -> None:
    if request.session.get("admin_authenticated") is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cần đăng nhập quản trị.")


def require_csrf(request: Request) -> None:
    require_admin(request)
    expected = request.session.get("csrf_token")
    received = request.headers.get("X-CSRF-Token")
    if not isinstance(expected, str) or not received or not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token không hợp lệ.")
