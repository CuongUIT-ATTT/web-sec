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
import time
from dataclasses import dataclass
from datetime import date
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
QUIESCENCE_REQUIRED_READS = 2
QUIESCENCE_INTERVAL_SECONDS = 1
QUIESCENCE_TIMEOUT_SECONDS = 10
REQUIRED_ROLE_NAMES = frozenset({"admin", "userA", "userB"})
MESSAGE_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
REVIEWER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._@-]{0,79}$")


@dataclass(frozen=True)
class HistorySnapshot:
    """Private, in-memory view of one stable target-history read."""

    message_classes: dict[str, str | None]


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


def _expected_rule_matrix(manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return the human-reviewed rule policy bound to the request manifest."""
    matrix: dict[str, dict[str, str]] = {}
    for request in manifest["allowed_requests"]:
        expectations = request.get("authorization_expectations")
        if not isinstance(expectations, dict):
            raise ZapContextError("ZAP allowlist has malformed authorization expectations.")
        matrix[request["path"]] = expectations
    return matrix


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
    fingerprint = attestation["context_sha256"]
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ZapContextError("Context attestation has an invalid SHA-256 fingerprint.")
    if fingerprint != context_sha256(context_path):
        raise ZapContextError("Imported Context fingerprint does not match its attestation.")
    reviewed_users = attestation["reviewed_users"]
    if (
        not isinstance(reviewed_users, list)
        or len(reviewed_users) != len(REQUIRED_ROLE_NAMES)
        or set(reviewed_users) != REQUIRED_ROLE_NAMES
    ):
        raise ZapContextError("Context attestation must review exactly admin, userA, and userB.")
    reviewed_paths = attestation["reviewed_paths"]
    if (
        not isinstance(reviewed_paths, list)
        or len(reviewed_paths) != len(allowed_paths(manifest))
        or set(reviewed_paths) != allowed_paths(manifest)
    ):
        raise ZapContextError("Context attestation paths do not match the exact allowlist.")
    expectations = attestation["access_rule_expectations"]
    if expectations != _expected_rule_matrix(manifest):
        raise ZapContextError("Context rule attestation does not match the reviewed allowlist policy.")
    reviewed_on = attestation["reviewed_on"]
    if not isinstance(reviewed_on, str):
        raise ZapContextError("Context attestation has invalid review metadata.")
    try:
        if date.fromisoformat(reviewed_on) > date.today():
            raise ZapContextError("Context attestation has invalid review metadata.")
    except ValueError as error:
        raise ZapContextError("Context attestation has invalid review metadata.") from error
    reviewer = attestation["reviewer"]
    if not isinstance(reviewer, str) or not REVIEWER_PATTERN.fullmatch(reviewer):
        raise ZapContextError("Context attestation has invalid review metadata.")
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
    """Return ZAP's canonical exact-path regex spelling for each reviewed URL."""
    return {
        f"{re.escape(TARGET_BASE)}{re.escape(path)}$".replace(r"\-", "-")
        for path in allowed_paths(manifest)
    }


def _loaded_context_metadata(api_key: str, context_name: str) -> dict[str, str]:
    """Read one exact Context by its reviewed name without changing ZAP state."""
    result = _zap_api(
        "context", "view", "context", {"contextName": context_name}, api_key=api_key
    )
    context = result.get("context")
    if not isinstance(context, dict):
        raise ZapContextError("ZAP did not return Context metadata.")
    context_id = context.get("id")
    if not isinstance(context_id, (str, int)) or not str(context_id):
        raise ZapContextError("ZAP Context metadata has no usable ID.")
    if context.get("name") != context_name:
        raise ZapContextError("ZAP Context name does not match its attestation.")
    return {"id": str(context_id), "name": context_name}


def _verify_context_include_regexes(
    api_key: str,
    manifest: dict[str, Any],
    context_name: str,
) -> int:
    """Require the exact reviewed include patterns without modifying the Context."""
    include_result = _zap_api(
        "context", "view", "includeRegexs", {"contextName": context_name}, api_key=api_key
    )
    include_regexs = include_result.get("includeRegexs")
    expected_patterns = _expected_include_patterns(manifest)
    if (
        not isinstance(include_regexs, list)
        or not all(isinstance(pattern, str) for pattern in include_regexs)
        or len(include_regexs) != len(expected_patterns)
        or set(include_regexs) != expected_patterns
    ):
        raise ZapContextError("ZAP Context include regexes are not exactly the reviewed paths.")
    return len(include_regexs)


def verify_imported_context(
    api_key: str,
    context_id: str,
    manifest: dict[str, Any],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    """Verify the just-imported Context’s identity and exact include regexes."""
    context_name = attestation["context_name"]
    context = _loaded_context_metadata(api_key, context_name)
    if context["id"] != str(context_id):
        raise ZapContextError("Imported Context ID cannot be verified.")
    include_count = _verify_context_include_regexes(api_key, manifest, context_name)
    return {"context_id": str(context_id), "context_name": context_name, "include_count": include_count}


def verify_preloaded_context(
    api_key: str,
    manifest: dict[str, Any],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    """Verify one already-loaded Desktop Context using only reviewed metadata."""
    context_name = attestation["context_name"]
    context = _loaded_context_metadata(api_key, context_name)
    include_count = _verify_context_include_regexes(api_key, manifest, context_name)
    return {"context_id": context["id"], "context_name": context_name, "include_count": include_count}


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
    raw_users = result.get("usersList")
    if not isinstance(raw_users, list):
        raise ZapContextError("ZAP did not return a user list.")
    users = [_normalise_user(user) for user in raw_users]
    names = [user["name"] for user in users]
    if len(users) != len(REQUIRED_ROLE_NAMES) or set(names) != set(attestation["reviewed_users"]):
        raise ZapContextError("Imported Context must contain exactly the reviewed users.")
    if len(set(names)) != len(names) or len({user["id"] for user in users}) != len(users):
        raise ZapContextError("Imported Context contains duplicate user identities.")
    return sorted(users, key=lambda user: user["name"])


_DESKTOP_AUTHENTICATION_STATE_KEYS = frozenset({
    "lastAuthFailure",
    "lastAuthHistoryId",
    "lastPollResult",
    "lastPollTimeInMs",
    "lastSuccessfulAuthTimeInMs",
    "requestsSinceLastPoll",
})


def _has_successful_authentication_state(result: Any) -> bool:
    """Accept only the reviewed successful response shapes from ZAP.

    ZAP installations expose the state either through the legacy
    ``authenticationState`` object or directly at the JSON response root. The
    strict shape check prevents unrelated or partial JSON from being mistaken
    for current authentication evidence.
    """
    if not isinstance(result, dict):
        return False
    if set(result) == {"authenticationState"}:
        state = result["authenticationState"]
        return (
            isinstance(state, dict)
            and set(state) == {"lastPollResult"}
            and state["lastPollResult"] in {True, "true"}
        )
    return (
        set(result) == _DESKTOP_AUTHENTICATION_STATE_KEYS
        and result["lastPollResult"] in {True, "true"}
    )


def verify_user_authentication_state(api_key: str, context_id: str, users: list[dict[str, str]]) -> list[dict[str, str]]:
    """Require ZAP to report an authenticated state for every reviewed user.

    This reads only the current polling result; it neither performs login
    requests nor exposes session/header data.
    """
    states: list[dict[str, str]] = []
    for user in users:
        result = _zap_api(
            "users", "view", "getAuthenticationState",
            {"contextId": context_id, "userId": user["id"]}, api_key=api_key,
        )
        if not _has_successful_authentication_state(result):
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


def wait_for_history_quiescence(
    api_key: str,
    *,
    timeout: int = QUIESCENCE_TIMEOUT_SECONDS,
    interval: int = QUIESCENCE_INTERVAL_SECONDS,
) -> dict[str, int]:
    """Require two stable target-history counts before capturing a baseline.

    This uses only ZAP's target-filtered Core count endpoint and sends no
    request to VAmPI. Counts and message identities remain private; the
    returned summary describes only the fixed observation policy.
    """
    if timeout < interval or interval <= 0:
        raise ZapContextError("ZAP history quiescence configuration is invalid.")
    deadline = time.monotonic() + timeout
    previous_count = _message_count(api_key)
    while True:
        if time.monotonic() + interval > deadline:
            raise ZapContextError("ZAP target history did not quiesce before the safe timeout.")
        time.sleep(interval)
        current_count = _message_count(api_key)
        if current_count == previous_count:
            return {
                "required_stable_reads": QUIESCENCE_REQUIRED_READS,
                "observation_interval_seconds": interval,
                "timeout_seconds": timeout,
            }
        previous_count = current_count


def get_messages_in_scope(api_key: str) -> list[dict[str, Any]]:
    """Retrieve the entire bounded target history using documented pagination."""
    total = _message_count(api_key)
    messages: list[dict[str, Any]] = []
    for start in range(0, total, MESSAGE_PAGE_SIZE):
        expected = min(MESSAGE_PAGE_SIZE, total - start)
        result = _zap_api(
            "core", "view", "messages",
            {"baseurl": TARGET_BASE, "start": str(start), "count": str(expected)},
            api_key=api_key,
        )
        page = result.get("messages")
        if not isinstance(page, list) or len(page) != expected:
            raise ZapContextError("ZAP history pagination is incomplete.")
        if not all(isinstance(message, dict) for message in page):
            raise ZapContextError("ZAP returned malformed message metadata.")
        messages.extend(page)
    if len(messages) != total or _message_count(api_key) != total:
        raise ZapContextError("ZAP target history changed during pagination.")
    return messages


def _message_id(message: dict[str, Any]) -> str:
    """Return a strict private identity for correlating one ZAP history record."""
    value = message.get("id")
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not MESSAGE_ID_PATTERN.fullmatch(value):
        raise ZapContextError("ZAP history contains an invalid message identity.")
    return value


def _approved_path_from_header(header: Any, manifest: dict[str, Any]) -> str | None:
    """Return an approved canonical path only when the request is exact."""
    if _classify_request_header(header, manifest) is not None:
        return None
    target = header.split("\r\n", 1)[0].split(" ", 2)[1]
    return urlsplit(target).path


def _capture_history_once(api_key: str, manifest: dict[str, Any]) -> HistorySnapshot:
    """Create an in-memory classified target-history snapshot without exporting it."""
    message_classes: dict[str, str | None] = {}
    for message in get_messages_in_scope(api_key):
        message_id = _message_id(message)
        if message_id in message_classes:
            raise ZapContextError("ZAP history contains duplicate message identities.")
        header = message.get("requestHeader")
        violation = _classify_request_header(header, manifest)
        message_classes[message_id] = violation or _approved_path_from_header(header, manifest)
    return HistorySnapshot(message_classes=message_classes)


def capture_history_snapshot(api_key: str, manifest: dict[str, Any]) -> HistorySnapshot:
    """Capture a stable target-history view using two identical identity reads."""
    first = _capture_history_once(api_key, manifest)
    second = _capture_history_once(api_key, manifest)
    if first.message_classes != second.message_classes:
        raise ZapContextError("ZAP target history did not remain stable while capturing a snapshot.")
    return first


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


def _is_access_url_seed_response(result: Any) -> bool:
    """Accept only ZAP Core's opaque non-null ``accessUrl`` envelope.

    The nested value can include raw request/response data, so it must never be
    inspected, retained, logged, or exported. The exact post-seed history delta
    remains the authoritative containment proof.
    """
    return (
        isinstance(result, dict)
        and set(result) == {"accessUrl"}
        and result["accessUrl"] is not None
    )


def seed_reviewed_paths(api_key: str, manifest: dict[str, Any]) -> dict[str, int]:
    """Add exactly the reviewed GET nodes after the private auth-history baseline.

    ``core.accessUrl`` is intentionally called once for each absolute
    allowlisted URL. It returns an opaque request/response envelope; only its
    non-null wrapper value is validated. The later strict history-delta gate proves
    this cannot turn into endpoint discovery or an incomplete seed delta.
    """
    seeded = 0
    for path in sorted(allowed_paths(manifest)):
        result = _zap_api(
            "core", "action", "accessUrl", {"url": f"{TARGET_BASE}{path}"}, api_key=api_key
        )
        if not _is_access_url_seed_response(result):
            raise ZapContextError("ZAP did not return a reviewed GET seed response.")
        seeded += 1
    return {"seeded_request_count": seeded}


def history_baseline_summary(snapshot: HistorySnapshot) -> dict[str, int]:
    """Return bounded provenance for a private post-auth history boundary."""
    return {"message_count": len(snapshot.message_classes)}


def _delta_classes(previous: HistorySnapshot, current: HistorySnapshot) -> dict[str, str | None]:
    """Return only new records after proving the current view extends the prior one."""
    previous_ids = set(previous.message_classes)
    current_ids = set(current.message_classes)
    if not previous_ids <= current_ids:
        raise ZapContextError("ZAP target history lost a prior message identity.")
    if any(current.message_classes[message_id] != classification for message_id, classification in previous.message_classes.items()):
        raise ZapContextError("ZAP target history changed a prior message classification.")
    return {
        message_id: classification
        for message_id, classification in current.message_classes.items()
        if message_id not in previous_ids
    }


def _delta_summary(
    previous: HistorySnapshot,
    current: HistorySnapshot,
    manifest: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """Classify a successor delta without persisting source records or identities."""
    allowed = allowed_paths(manifest)
    path_counts = {path: 0 for path in sorted(allowed)}
    violations: dict[str, int] = {}
    delta = _delta_classes(previous, current)
    for classification in delta.values():
        if classification in allowed:
            path_counts[classification] += 1
        else:
            violation = classification or "missing_request_header"
            violations[violation] = violations.get(violation, 0) + 1
    return not violations, {
        "baseline_message_count": len(previous.message_classes),
        "new_message_count": len(delta),
        "approved_path_counts": path_counts,
        "violation_counts": violations,
    }


def verify_history_delta(
    previous: HistorySnapshot,
    current: HistorySnapshot,
    manifest: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """Require all traffic introduced after a private baseline to be approved GETs."""
    return _delta_summary(previous, current, manifest)


def verify_seed_delta(
    previous: HistorySnapshot,
    current: HistorySnapshot,
    manifest: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    """Require exactly one newly observed approved GET for every reviewed path."""
    contained, summary = _delta_summary(previous, current, manifest)
    if summary["approved_path_counts"] != {path: 1 for path in sorted(allowed_paths(manifest))}:
        violations = summary["violation_counts"]
        violations["unexpected_seed_path_count"] = 1
        contained = False
    return contained, summary
