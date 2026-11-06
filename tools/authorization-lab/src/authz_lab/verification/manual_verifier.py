"""Independently re-verify known VAmPI book fixtures with read-only GET requests."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ALLOWED_BASE_URL = "http://127.0.0.1:5000"


class VerificationSafetyError(ValueError):
    """Raised before an unsafe verification request is attempted."""


def _validate_base_url(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 5000
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise VerificationSafetyError(f"Base URL must be exactly {ALLOWED_BASE_URL}.")


def _url_for_path(base_url: str, path: str) -> str:
    _validate_base_url(base_url)
    parsed = urlsplit(path)
    if not path.startswith("/") or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise VerificationSafetyError("Verification paths must be local absolute paths without query or fragment.")
    return ALLOWED_BASE_URL + "/".join(quote(segment, safe="") for segment in path.split("/"))


def _get(path: str, token: str | None, base_url: str) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = token
    start = time.perf_counter()
    request = Request(_url_for_path(base_url, path), headers=headers, method="GET")
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read()
            status = response.status
    except HTTPError as error:
        body = error.read()
        status = error.code
    except URLError as error:
        return {
            "status_code": None,
            "response_json": None,
            "request_duration_ms": round((time.perf_counter() - start) * 1000, 3),
            "error": f"Network error: {error.reason}",
        }
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    return {
        "status_code": status,
        "response_json": payload,
        "request_duration_ms": round((time.perf_counter() - start) * 1000, 3),
        "error": None,
    }


def load_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _book_fixtures(ownership: list[dict[str, str]]) -> list[dict[str, str]]:
    return [fixture for fixture in ownership if fixture.get("resource_type") == "book"]


def _book_path(fixture: dict[str, str]) -> str:
    template = fixture["path_template"]
    if template != "/books/v1/{book_title}":
        raise VerificationSafetyError(f"Unexpected book fixture template: {template}")
    return template.replace("{book_title}", fixture["resource_id"])


def _owner_baseline_is_valid(response: dict[str, Any], fixture: dict[str, str]) -> bool:
    body = response.get("response_json")
    return (
        response.get("status_code") == 200
        and isinstance(body, dict)
        and body.get("book_title") == fixture["resource_id"]
        and body.get("owner") == fixture["owner_username"]
        and isinstance(body.get("secret"), str)
        and bool(body["secret"])
    )


def _is_admin_role(role_name: str, role_entry: dict[str, Any] | None = None) -> bool:
    if isinstance(role_entry, dict) and "is_admin" in role_entry:
        return bool(role_entry["is_admin"])
    return role_name.startswith("admin")


def _access_direction(actor_is_admin: bool, owner_is_admin: bool) -> str:
    if not actor_is_admin and not owner_is_admin:
        return "USER_TO_USER"
    if not actor_is_admin and owner_is_admin:
        return "USER_TO_ADMIN"
    if actor_is_admin and not owner_is_admin:
        return "ADMIN_TO_USER"
    return "ADMIN_TO_ADMIN"


def verify_debug_endpoint(base_url: str = ALLOWED_BASE_URL) -> dict[str, Any]:
    """Independently check whether GET /users/v1/_debug exposes credentials without authentication."""
    _validate_base_url(base_url)
    response = _get("/users/v1/_debug", None, base_url)
    body = response.get("response_json")
    users = body.get("users") if isinstance(body, dict) else None
    exposes_passwords = (
        response.get("status_code") == 200
        and isinstance(users, list)
        and bool(users)
        and all(isinstance(u, dict) and "password" in u and "admin" in u for u in users)
    )
    return {
        "fixture_id": "users-v1-_debug",
        "endpoint": "/users/v1/_debug",
        "owner_role": "admin",
        "actor_role": "anonymous",
        "access_direction": "ANONYMOUS_TO_SYSTEM",
        "method": "GET",
        "status_code": response["status_code"],
        "request_duration_ms": response["request_duration_ms"],
        "user_record_count": len(users) if isinstance(users, list) else 0,
        "exposes_plaintext_passwords_and_admin_flags": exposes_passwords,
        "outcome": "CONFIRMED_EXCESSIVE_DATA_EXPOSURE" if exposes_passwords else "NOT_REPRODUCED",
        "error": response["error"],
    }


def independently_verify_books(
    roles_config: dict[str, dict[str, str]], ownership: list[dict[str, str]], base_url: str = ALLOWED_BASE_URL
) -> list[dict[str, Any]]:
    """Re-fetch owner baselines and compare cross-user JSON directly, never using Week 2 verdict fields."""
    _validate_base_url(base_url)
    records: list[dict[str, Any]] = []
    all_books = _book_fixtures(ownership)
    active_books = [fixture for fixture in all_books if fixture.get("owner_role") in roles_config]
    if all_books and not active_books:
        raise ValueError("No book fixture owner roles matched the active role configuration.")
    for fixture in active_books:
        owner_role = fixture["owner_role"]
        path = _book_path(fixture)
        owner_response = _get(path, roles_config[owner_role]["token"], base_url)
        owner_valid = _owner_baseline_is_valid(owner_response, fixture)
        owner_secret = owner_response.get("response_json", {}).get("secret") if owner_valid else None
        owner_is_admin = _is_admin_role(owner_role, roles_config.get(owner_role))

        for actor_role in sorted(roles_config):
            if actor_role == owner_role:
                continue
            actor_response = _get(path, roles_config[actor_role]["token"], base_url)
            body = actor_response.get("response_json")
            matches_owner_secret = (
                owner_valid
                and actor_response.get("status_code") == 200
                and isinstance(body, dict)
                and body.get("book_title") == fixture["resource_id"]
                and body.get("owner") == fixture["owner_username"]
                and body.get("secret") == owner_secret
            )
            actor_is_admin = _is_admin_role(actor_role, roles_config.get(actor_role))
            direction = _access_direction(actor_is_admin, owner_is_admin)
            policy_dependent = actor_is_admin
            outcome = (
                "CONFIRMED_USER_TO_ADMIN_BOLA"
                if matches_owner_secret and not policy_dependent and owner_is_admin
                else "CONFIRMED_USER_TO_USER_BOLA"
                if matches_owner_secret and not policy_dependent
                else "POLICY_DEPENDENT_ADMIN_ACCESS"
                if matches_owner_secret and policy_dependent
                else "NOT_REPRODUCED"
            )
            records.append(
                {
                    "fixture_id": fixture["resource_id"],
                    "endpoint": path,
                    "owner_role": owner_role,
                    "actor_role": actor_role,
                    "access_direction": direction,
                    "method": "GET",
                    "owner_baseline_valid": owner_valid,
                    "owner_status_code": owner_response["status_code"],
                    "status_code": actor_response["status_code"],
                    "request_duration_ms": actor_response["request_duration_ms"],
                    "response_shape": sorted(body) if isinstance(body, dict) else None,
                    "secret_matches_fresh_owner_baseline": matches_owner_secret,
                    "outcome": outcome,
                    "error": actor_response["error"],
                }
            )
    if any(fixture.get("resource_type") == "user_profile" for fixture in ownership):
        records.append(verify_debug_endpoint(base_url))
    return records
