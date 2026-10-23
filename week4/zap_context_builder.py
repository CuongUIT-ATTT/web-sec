"""Fail-closed helpers for the reviewed local ZAP Access Control assessment.

The Access Control add-on cannot create or edit access rules through its API.
This module therefore imports a *reviewed* ZAP Context and proves only
non-secret facts about it before a scan can start. It never creates users,
access rules, credentials, or generic scan targets.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from vampi_authz_lab.common import read_json
from vampi_authz_lab.zap_allowlist import ZapAllowlistError, load_zap_allowlist

ZAP_API_BASE = "http://127.0.0.1:8080"
TARGET_BASE = "http://127.0.0.1:5000"
FORBIDDEN_PATHS = frozenset({"/createdb"})
ALLOWED_METHODS = frozenset({"GET"})
MESSAGE_PAGE_SIZE = 100
MAX_MESSAGES = 1_000
REQUIRED_ROLE_NAMES = frozenset({"admin", "userA", "userB"})


class ZapContextError(ValueError):
    """Raised when the limited local ZAP assessment cannot proceed safely."""


def _safe_api_error(error: HTTPError) -> ZapContextError:
    """Return bounded metadata without reading a potentially sensitive body."""
    return ZapContextError(f"ZAP API rejected the request (HTTP {error.code}).")


def _zap_api(
    component: str,
    action_type: str,
    action: str,
    params: dict[str, str] | None = None,
    *,
    api_key: str = "",
) -> Any:
    """Call a local ZAP JSON endpoint without retaining error response bodies."""
    query = {"apikey": api_key}
    if params:
        query.update(params)
    url = f"{ZAP_API_BASE}/JSON/{component}/{action_type}/{action}/?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read(65_536)
    except HTTPError as error:
        raise _safe_api_error(error) from error
    except URLError as error:
        reason_type = type(error.reason).__name__ if error.reason else "unknown"
        raise ZapContextError(f"ZAP daemon unreachable ({reason_type}).") from error
    except OSError as error:
        raise ZapContextError(f"ZAP transport failure ({type(error).__name__}).") from error

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ZapContextError("ZAP API returned invalid JSON.") from error
    if not isinstance(decoded, dict):
        raise ZapContextError("ZAP API returned an unexpected JSON shape.")
    return decoded


def load_allowlist_v2(path: str | Path) -> dict[str, Any]:
    """Load the narrow manifest through the shared strict allowlist validator."""
    try:
        manifest = load_zap_allowlist(path)
    except ZapAllowlistError as error:
        raise ZapContextError(str(error)) from error
    if manifest.get("schema_version") != 2:
        raise ZapContextError("ZAP allowlist-v2 must use schema_version 2.")
    return manifest


def allowed_paths(manifest: dict[str, Any]) -> set[str]:
    """Return exactly the reviewed URL paths."""
    return {entry["path"] for entry in manifest["allowed_requests"]}


def allowed_urls(manifest: dict[str, Any]) -> set[str]:
    """Return exactly the reviewed absolute URLs."""
    return {f"{TARGET_BASE}{path}" for path in allowed_paths(manifest)}


def _assert_private_file(path: str | Path, label: str) -> Path:
    source = Path(path)
    if not source.is_file():
        raise ZapContextError(f"{label} does not exist.")
    if source.is_symlink():
        raise ZapContextError(f"{label} must not be a symbolic link.")
    mode = stat.S_IMODE(source.stat().st_mode)
    if mode != 0o600:
        raise ZapContextError(f"{label} must have permission mode 0600.")
    return source


def context_sha256(context_path: str | Path) -> str:
    """Return the fingerprint of a checked private imported Context file."""
    source = _assert_private_file(context_path, "Imported ZAP Context")
    return hashlib.sha256(source.read_bytes()).hexdigest()


def load_context_attestation(
    path: str | Path,
    manifest: dict[str, Any],
    context_path: str | Path,
) -> dict[str, Any]:
    """Validate the non-secret review record bound to the local Context file."""
    attestation = read_json(path)
    if not isinstance(attestation, dict):
        raise ZapContextError("Context attestation must be a JSON object.")
    required = {
        "schema_version",
        "context_name",
        "target",
        "context_sha256",
        "reviewed_users",
        "reviewed_paths",
        "access_rule_expectations",
        "reviewed_on",
        "reviewer",
    }
    missing = required - set(attestation)
    if missing:
        raise ZapContextError("Context attestation is missing required review fields.")
    if attestation["schema_version"] != 1:
        raise ZapContextError("Unsupported Context attestation schema version.")
    if attestation["target"] != TARGET_BASE:
        raise ZapContextError("Context attestation target is not the approved local origin.")
    if attestation["context_name"] != manifest.get("context_name"):
        raise ZapContextError("Context attestation name does not match the allowlist.")
    if not isinstance(attestation["context_sha256"], str) or len(attestation["context_sha256"]) != 64:
        raise ZapContextError("Context attestation has an invalid SHA-256 fingerprint.")
    if attestation["context_sha256"] != context_sha256(context_path):
        raise ZapContextError("Imported Context fingerprint does not match its attestation.")
    reviewed_users = attestation["reviewed_users"]
    if not isinstance(reviewed_users, list) or set(reviewed_users) != REQUIRED_ROLE_NAMES:
        raise ZapContextError("Context attestation must review exactly admin, userA, and userB.")
    reviewed_paths = attestation["reviewed_paths"]
    if not isinstance(reviewed_paths, list) or set(reviewed_paths) != allowed_paths(manifest):
        raise ZapContextError("Context attestation paths do not match the exact allowlist.")
    expectations = attestation["access_rule_expectations"]
    if not isinstance(expectations, dict) or set(expectations) != allowed_paths(manifest):
        raise ZapContextError("Context attestation must cover every reviewed path.")
    for path_value, per_user in expectations.items():
        if not isinstance(per_user, dict) or set(per_user) != REQUIRED_ROLE_NAMES:
            raise ZapContextError(f"Context rule attestation is incomplete for {path_value}.")
        if any(value not in {"allowed", "denied", "policy-dependent"} for value in per_user.values()):
            raise ZapContextError("Context rule attestation contains an invalid expectation.")
    return attestation


def import_reviewed_context(api_key: str, zap_context_path: str) -> str:
    """Import the operator-reviewed Context file visible inside the ZAP host."""
    if not isinstance(zap_context_path, str) or not zap_context_path.startswith("/"):
        raise ZapContextError("ZAP Context path must be an absolute in-container path.")
    result = _zap_api(
        "context", "action", "importContext", {"contextFile": zap_context_path}, api_key=api_key
    )
    context_id = result.get("contextId")
    if not isinstance(context_id, (str, int)) or not str(context_id):
        raise ZapContextError("ZAP did not return an imported Context ID.")
    return str(context_id)


def _expected_include_patterns(manifest: dict[str, Any]) -> set[str]:
    return {
        f"{re.escape(TARGET_BASE)}{re.escape(path)}$"
        for path in allowed_paths(manifest)
    }


def verify_imported_context(
    api_key: str,
    context_id: str,
    manifest: dict[str, Any],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    """Verify the imported Context’s name and exact include regexes."""
    result = _zap_api("context", "view", "context", {"contextId": context_id}, api_key=api_key)
    context = result.get("context")
    if not isinstance(context, dict):
        raise ZapContextError("ZAP did not return Context metadata.")
    if str(context.get("id")) != str(context_id):
        raise ZapContextError("Imported Context ID cannot be verified.")
    if context.get("name") != attestation["context_name"]:
        raise ZapContextError("Imported Context name does not match its attestation.")
    include_result = _zap_api(
        "context", "view", "includeRegexs", {"contextName": attestation["context_name"]}, api_key=api_key
    )
    include_regexs = include_result.get("includeRegexs")
    if not isinstance(include_regexs, list) or set(include_regexs) != _expected_include_patterns(manifest):
        raise ZapContextError("Imported Context include regexes are not exactly the reviewed paths.")
    return {"context_id": str(context_id), "context_name": attestation["context_name"], "include_count": len(include_regexs)}


def _normalise_user(raw_user: Any) -> dict[str, str]:
    if not isinstance(raw_user, dict):
        raise ZapContextError("ZAP returned malformed user metadata.")
    user_id = raw_user.get("id")
    name = raw_user.get("name")
    enabled = raw_user.get("enabled")
    if not isinstance(user_id, (str, int)) or not str(user_id) or not isinstance(name, str):
        raise ZapContextError("ZAP user metadata is incomplete.")
    if enabled not in {True, "true", "True", "TRUE"}:
        raise ZapContextError("Imported ZAP user is disabled.")
    return {"id": str(user_id), "name": name}


def verify_imported_users(api_key: str, context_id: str, attestation: dict[str, Any]) -> list[dict[str, str]]:
    """Verify exactly the reviewed enabled users without requesting credentials."""
    result = _zap_api("users", "view", "usersList", {"contextId": context_id}, api_key=api_key)
    raw_users = result.get("users")
    if not isinstance(raw_users, list):
        raise ZapContextError("ZAP did not return a user list.")
    users = [_normalise_user(user) for user in raw_users]
    names = [user["name"] for user in users]
    if len(users) != len(REQUIRED_ROLE_NAMES) or set(names) != set(attestation["reviewed_users"]):
        raise ZapContextError("Imported Context must contain exactly the reviewed users.")
    if len(set(names)) != len(names) or len({user["id"] for user in users}) != len(users):
        raise ZapContextError("Imported Context contains duplicate user identities.")
    return sorted(users, key=lambda user: user["name"])


def verify_user_authentication_state(api_key: str, context_id: str, users: list[dict[str, str]]) -> list[dict[str, str]]:
    """Require ZAP to report an authenticated state for every reviewed user.

    This reads only the boolean authentication state; it neither performs login
    requests nor exposes session/header data.
    """
    states: list[dict[str, str]] = []
    for user in users:
        result = _zap_api(
            "users", "view", "getAuthenticationState",
            {"contextId": context_id, "userId": user["id"]}, api_key=api_key,
        )
        state = result.get("authenticationState")
        if state not in {True, "true", "True", "TRUE", "authenticated", "AUTHENTICATED"}:
            raise ZapContextError("A reviewed ZAP user is not authenticated.")
        states.append({"name": user["name"], "state": "authenticated"})
    return states


def get_site_tree_urls(api_key: str) -> list[str]:
    """Retrieve Site Tree values only for non-blocking structural diagnostics."""
    result = _zap_api("core", "view", "sites", api_key=api_key)
    sites = result.get("sites")
    if not isinstance(sites, list) or not all(isinstance(site, str) for site in sites):
        raise ZapContextError("ZAP returned malformed Site Tree metadata.")
    return sites


def verify_site_tree_containment(api_key: str, manifest: dict[str, Any]) -> tuple[bool, dict[str, int]]:
    """Classify Site Tree structure without using it as a scan gate.

    The boolean is deliberately always true after successful metadata retrieval.
    Actual HTTP-message history is the only URL/method containment gate.
    """
    allowed = allowed_urls(manifest)
    parent_prefixes = {TARGET_BASE, f"{TARGET_BASE}/"}
    for path in allowed_paths(manifest):
        pieces = path.strip("/").split("/")
        for index in range(1, len(pieces)):
            parent_prefixes.add(f"{TARGET_BASE}/{'/'.join(pieces[:index])}")
    diagnostics = {"allowed_nodes": 0, "structural_parent_nodes": 0, "other_nodes": 0}
    for url in get_site_tree_urls(api_key):
        if url in allowed:
            diagnostics["allowed_nodes"] += 1
        elif url in parent_prefixes:
            diagnostics["structural_parent_nodes"] += 1
        else:
            diagnostics["other_nodes"] += 1
    return True, diagnostics


def _message_count(api_key: str) -> int:
    result = _zap_api("core", "view", "numberOfMessages", {"baseurl": TARGET_BASE}, api_key=api_key)
    value = result.get("numberOfMessages")
    try:
        count = int(value)
    except (TypeError, ValueError) as error:
        raise ZapContextError("ZAP returned an invalid message count.") from error
    if count < 0 or count > MAX_MESSAGES:
        raise ZapContextError("ZAP message count is outside the safe assessment limit.")
    return count


def get_messages_in_scope(api_key: str) -> list[dict[str, Any]]:
    """Retrieve the entire bounded target history using documented pagination."""
    total = _message_count(api_key)
    messages: list[dict[str, Any]] = []
    for start in range(0, total, MESSAGE_PAGE_SIZE):
        result = _zap_api(
            "core", "view", "messages",
            {"baseurl": TARGET_BASE, "start": str(start), "count": str(min(MESSAGE_PAGE_SIZE, total - start))},
            api_key=api_key,
        )
        page = result.get("messages")
        if not isinstance(page, list):
            raise ZapContextError("ZAP returned an invalid message page.")
        if not page or len(page) > min(MESSAGE_PAGE_SIZE, total - start):
            raise ZapContextError("ZAP history pagination is incomplete.")
        if not all(isinstance(message, dict) for message in page):
            raise ZapContextError("ZAP returned malformed message metadata.")
        messages.extend(page)
    if len(messages) != total:
        raise ZapContextError("ZAP history pagination did not return every message.")
    return messages


def _classify_request_header(header: Any, manifest: dict[str, Any]) -> str | None:
    """Return a bounded violation code or ``None`` for an exact approved GET."""
    if not isinstance(header, str):
        return "missing_request_header"
    first_line = header.split("\r\n", 1)[0]
    fields = first_line.split(" ")
    if len(fields) != 3 or not all(fields):
        return "malformed_request_line"
    method, target, version = fields
    if version not in {"HTTP/1.0", "HTTP/1.1", "HTTP/2", "HTTP/2.0"}:
        return "malformed_request_line"
    if method != "GET":
        return "non_get_method"
    parsed = urlsplit(target)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 5000
        or parsed.username is not None
        or parsed.password is not None
    ):
        return "foreign_origin"
    if parsed.query or parsed.fragment:
        return "query_or_fragment"
    if parsed.path in FORBIDDEN_PATHS or "createdb" in parsed.path:
        return "forbidden_path"
    if parsed.path not in allowed_paths(manifest):
        return "unapproved_path"
    return None


def seed_reviewed_paths(api_key: str, manifest: dict[str, Any]) -> dict[str, int]:
    """Add exactly the reviewed GET nodes to a fresh ZAP Site Tree.

    ``core.accessUrl`` is intentionally called once for each absolute
    allowlisted URL. The fresh-history gate in the runner plus later paginated
    history validation ensures this cannot turn into endpoint discovery.
    """
    seeded = 0
    for path in sorted(allowed_paths(manifest)):
        result = _zap_api(
            "core", "action", "accessUrl", {"url": f"{TARGET_BASE}{path}"}, api_key=api_key
        )
        if result.get("Result") != "OK":
            raise ZapContextError("ZAP did not confirm a reviewed GET seed request.")
        seeded += 1
    return {"seeded_request_count": seeded}


def verify_message_containment(
    api_key: str,
    manifest: dict[str, Any],
    *,
    expected_count: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Fail closed unless every actual local-target message is an approved GET.

    ``expected_count`` is used for the fresh-session baseline and exact seed
    phase. The returned diagnostic deliberately contains counts and bounded
    reason codes only; it never exposes headers, request targets, query values,
    or bodies.
    """
    violations: dict[str, int] = {}
    message_count = 0
    for message in get_messages_in_scope(api_key):
        message_count += 1
        violation = _classify_request_header(message.get("requestHeader"), manifest)
        if violation:
            violations[violation] = violations.get(violation, 0) + 1
    if expected_count is not None and message_count != expected_count:
        violations["unexpected_message_count"] = abs(message_count - expected_count) or 1
    return not violations, {
        "message_count": message_count,
        "violation_counts": violations,
    }
