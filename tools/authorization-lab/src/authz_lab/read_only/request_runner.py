"""Run safe, local-only VAmPI read requests without recording credentials."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ALLOWED_BASE_URL = "http://127.0.0.1:5000"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
FORBIDDEN_PATHS = {"/createdb"}
MAX_BODY_BYTES = 16_384
INVALID_LOCAL_TOKEN = "Bearer " + "invalid-local-lab-token"


class SafetyError(ValueError):
    """Raised before a request that fails the local-lab safety policy."""


def validate_base_url(base_url: str) -> str:
    """Require precisely the authorized local VAmPI origin."""
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
        raise SafetyError(f"Base URL must be exactly {ALLOWED_BASE_URL}.")
    return ALLOWED_BASE_URL


def concrete_url(base_url: str, endpoint: str) -> str:
    """Build an allowed URL from an absolute API path, escaping each segment."""
    validate_base_url(base_url)
    parsed = urlsplit(endpoint)
    if not endpoint.startswith("/") or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        raise SafetyError("Test endpoint must be an absolute path without query or fragment.")
    escaped_path = "/".join(quote(segment, safe="") for segment in endpoint.split("/"))
    return ALLOWED_BASE_URL + escaped_path


def _parse_body(body: bytes) -> tuple[Any | None, str | None]:
    decoded = body[:MAX_BODY_BYTES].decode("utf-8", errors="replace")
    try:
        return json.loads(decoded), None
    except json.JSONDecodeError:
        return None, decoded


def _response_record(status_code: int | None, headers: Any, body: bytes, error: str | None = None) -> dict[str, Any]:
    response_json, response_text = _parse_body(body)
    return {
        "status_code": status_code,
        "content_type": headers.get("Content-Type", "") if headers else "",
        "content_length": len(body),
        "response_json": response_json,
        "response_text": response_text,
        "body_truncated": len(body) > MAX_BODY_BYTES,
        "error": error,
    }


def send_read_request(
    method: str,
    endpoint: str,
    base_url: str,
    token: str | None = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Issue one permitted read-only request and return a credential-free record."""
    normalized_method = method.upper()
    if normalized_method not in SAFE_METHODS:
        raise SafetyError(f"State-changing method {normalized_method} is disabled.")
    if endpoint in FORBIDDEN_PATHS:
        raise SafetyError(f"Endpoint {endpoint} is permanently forbidden.")

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = token
    request = Request(concrete_url(base_url, endpoint), headers=headers, method=normalized_method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return _response_record(response.status, response.headers, response.read())
    except HTTPError as error:
        return _response_record(error.code, error.headers, error.read())
    except URLError as error:
        return _response_record(None, None, b"", error=f"Network error: {error.reason}")
    except TimeoutError:
        return _response_record(None, None, b"", error="Request timed out")


def load_roles_config(path: str | Path) -> dict[str, dict[str, str]]:
    """Load role configuration without ever returning its values for logging."""
    with Path(path).open(encoding="utf-8") as handle:
        roles = json.load(handle)
    if not isinstance(roles, dict) or not roles:
        raise ValueError("Role configuration must be a non-empty JSON object.")
    for name, role in roles.items():
        if not isinstance(name, str) or not isinstance(role, dict):
            raise ValueError("Role configuration contains an invalid role.")
        token = role.get("token")
        username = role.get("username")
        if not isinstance(token, str) or not token.startswith("Bearer ") or not isinstance(username, str):
            raise ValueError(f"Role configuration for '{name}' is invalid.")
    return roles


def preflight(
    roles_config: dict[str, dict[str, str]], fixtures: list[dict[str, str]], base_url: str
) -> dict[str, Any]:
    """Confirm the target, role tokens, and owner book fixtures before test execution."""
    validate_base_url(base_url)
    findings: list[str] = []
    root = send_read_request("GET", "/", base_url)
    if root["status_code"] != 200 or not isinstance(root["response_json"], dict) or root["response_json"].get("vulnerable") != 1:
        findings.append("The target did not confirm VAmPI vulnerable mode (vulnerable=1).")

    for role_name, role in roles_config.items():
        result = send_read_request("GET", "/me", base_url, role["token"])
        response_data = result.get("response_json", {}).get("data") if isinstance(result.get("response_json"), dict) else None
        if result["status_code"] != 200 or not isinstance(response_data, dict) or response_data.get("username") != role["username"]:
            findings.append(f"Role preflight failed for '{role_name}'; renew its local token.")

    for fixture in fixtures:
        if fixture["resource_type"] != "book":
            continue
        owner = fixture["owner_role"]
        if owner not in roles_config:
            findings.append(f"Book fixture '{fixture['resource_id']}' has an unknown owner role.")
            continue
        result = send_read_request(
            "GET",
            fixture["path_template"].replace("{book_title}", fixture["resource_id"]),
            base_url,
            roles_config[owner]["token"],
        )
        if result["status_code"] != 200:
            findings.append(f"Owner fixture check failed for book '{fixture['resource_id']}'.")

    if findings:
        raise RuntimeError("Preflight failed: " + " ".join(findings))
    return {"target": ALLOWED_BASE_URL, "roles_verified": sorted(roles_config), "book_fixtures_verified": sum(f["resource_type"] == "book" for f in fixtures)}


def run_all_tests(
    matrix: list[dict[str, Any]], roles_config: dict[str, dict[str, str]], base_url: str, delay: float = 0.15
) -> list[dict[str, Any]]:
    """Execute enabled read-only cases and store no request headers or tokens."""
    results: list[dict[str, Any]] = []
    for case in matrix:
        if not case.get("enabled_read_only"):
            results.append({**case, "skipped": True, "skip_reason": "Not enabled in read-only mode."})
            continue
        scenario = case["scenario"]
        token: str | None = None
        if scenario not in {"anonymous", "anonymous_observation", "invalid_token"}:
            actor = case["actor_role"]
            token = roles_config[actor]["token"]
        elif scenario == "invalid_token":
            token = INVALID_LOCAL_TOKEN
        result = send_read_request(case["method"], case["endpoint"], base_url, token)
        results.append({**case, **result, "skipped": False})
        time.sleep(delay)
    return results
