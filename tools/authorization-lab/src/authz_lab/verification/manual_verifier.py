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


def independently_verify_books(
    roles_config: dict[str, dict[str, str]], ownership: list[dict[str, str]], base_url: str = ALLOWED_BASE_URL
) -> list[dict[str, Any]]:
    """Re-fetch owner baselines and compare cross-user JSON directly, never using Week 2 verdict fields."""
    _validate_base_url(base_url)
    records: list[dict[str, Any]] = []
    for fixture in _book_fixtures(ownership):
        owner_role = fixture["owner_role"]
        if owner_role not in roles_config:
            raise ValueError(f"Fixture owner role '{owner_role}' is absent from role configuration.")
        path = _book_path(fixture)
        owner_response = _get(path, roles_config[owner_role]["token"], base_url)
        owner_valid = _owner_baseline_is_valid(owner_response, fixture)
        owner_secret = owner_response.get("response_json", {}).get("secret") if owner_valid else None

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
            policy_dependent = actor_role == "admin"
            outcome = (
                "CONFIRMED_USER_TO_USER_BOLA"
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
    return records
