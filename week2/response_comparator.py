"""Analyze authorization results using structured, nested JSON evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

DYNAMIC_FIELDS = {"timestamp", "request_id", "created_at", "updated_at"}
SENSITIVE_FIELD_NAMES = {"secret", "password", "token", "auth_token"}


def normalize_json(value: Any) -> Any:
    """Remove dynamic fields recursively and sort mappings into stable structures."""
    if isinstance(value, Mapping):
        return {
            key: normalize_json(child)
            for key, child in sorted(value.items())
            if key not in DYNAMIC_FIELDS
        }
    if isinstance(value, list):
        return [normalize_json(item) for item in value]
    return value


def flatten_json(value: Any, prefix: str = "$") -> dict[str, Any]:
    """Map leaf JSON values to path keys for explainable evidence comparison."""
    leaves: dict[str, Any] = {}
    if isinstance(value, Mapping):
        for key, child in value.items():
            leaves.update(flatten_json(child, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.update(flatten_json(child, f"{prefix}[{index}]"))
    else:
        leaves[prefix] = value
    return leaves


def json_similarity(left: Any, right: Any) -> float:
    """Return Jaccard similarity across stable JSON leaf path/value signatures."""
    left_leaves = flatten_json(normalize_json(left))
    right_leaves = flatten_json(normalize_json(right))
    left_set = {json.dumps([path, value], sort_keys=True, default=str) for path, value in left_leaves.items()}
    right_set = {json.dumps([path, value], sort_keys=True, default=str) for path, value in right_leaves.items()}
    if not left_set and not right_set:
        return 1.0
    return round(len(left_set & right_set) / len(left_set | right_set), 3)


def _sensitive_matches(response_json: Any, baseline_json: Any) -> list[str]:
    response_leaves = flatten_json(normalize_json(response_json))
    baseline_leaves = flatten_json(normalize_json(baseline_json))
    matches: list[str] = []
    for path, value in response_leaves.items():
        field_name = path.rsplit(".", 1)[-1].lower()
        if field_name in SENSITIVE_FIELD_NAMES and baseline_leaves.get(path) == value:
            matches.append(path)
    return matches


def _sanitize_and_extract_debug_exposure(response_json: Any) -> tuple[Any, list[str]]:
    """Ensure debug responses keep only user_record_count and exposed_field_names, never password values."""
    if isinstance(response_json, dict) and isinstance(response_json.get("users"), list):
        users = response_json["users"]
        field_names = sorted({str(key) for user in users if isinstance(user, dict) for key in user.keys()})
        sanitized = {
            "user_record_count": len(users),
            "exposed_field_names": field_names,
        }
        sensitive = [f"$.users[*].{field}" for field in field_names if field.lower() in SENSITIVE_FIELD_NAMES]
        return sanitized, sensitive
    if (
        isinstance(response_json, dict)
        and isinstance(response_json.get("user_record_count"), int)
        and isinstance(response_json.get("exposed_field_names"), list)
    ):
        field_names = [str(field) for field in response_json["exposed_field_names"]]
        sensitive = (
            [f"$.users[*].{field}" for field in field_names if field.lower() in SENSITIVE_FIELD_NAMES]
            if response_json["user_record_count"] > 0
            else []
        )
        return response_json, sensitive
    return response_json, _standalone_sensitive_paths(response_json)


def analyze_result(result: dict[str, Any], baseline: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify one case without treating a successful status alone as proof."""
    analyzed = dict(result)
    if result.get("skipped"):
        analyzed.update(verdict="SKIPPED", reasons=[result.get("skip_reason", "Case was skipped.")])
        return analyzed

    category = result["risk_category"]
    status = result.get("status_code")
    response_json = result.get("response_json")

    if category == "PUBLIC_OBJECT_READ":
        analyzed.update(
            verdict="OBSERVATION",
            reasons=["Operation is public in the supplied OpenAPI document; recorded without an authorization expectation."],
        )
        return analyzed

    if result["scenario"] == "owner_control":
        verdict = "CONTROL_PASS" if status and 200 <= status < 300 else "INCONCLUSIVE"
        reason = "Owner control succeeded." if verdict == "CONTROL_PASS" else "Owner control failed; cross-user cases cannot be trusted."
        analyzed.update(verdict=verdict, reasons=[reason])
        return analyzed

    if status in {401, 403, 404}:
        analyzed.update(verdict="DENIED", reasons=[f"Access was denied or hidden with HTTP {status}."])
        return analyzed
    if status is None:
        analyzed.update(verdict="INCONCLUSIVE", reasons=[result.get("error") or "No HTTP response received."])
        return analyzed
    if not (200 <= status < 300):
        analyzed.update(verdict="INCONCLUSIVE", reasons=[f"Unexpected HTTP status {status}."])
        return analyzed

    baseline_json = baseline.get("response_json") if baseline else None
    similarity = json_similarity(response_json, baseline_json) if baseline_json is not None else None
    sensitive_paths = _sensitive_matches(response_json, baseline_json) if baseline_json is not None else []
    analyzed["similarity_to_owner_baseline"] = similarity
    analyzed["evidence_paths"] = sensitive_paths

    if category == "BOLA" and result["scenario"] == "cross_user" and sensitive_paths:
        analyzed.update(
            verdict="CONFIRMED",
            reasons=[
                "Cross-user request succeeded and returned sensitive owner-baseline data at "
                + ", ".join(sensitive_paths)
                + "."
            ],
        )
    elif category in {"EXCESSIVE_DATA_EXPOSURE", "BFLA_DEBUG_EXPOSURE"}:
        sanitized_json, standalone_paths = _sanitize_and_extract_debug_exposure(response_json)
        analyzed["response_json"] = sanitized_json
        analyzed["response_text"] = None
        analyzed["evidence_paths"] = standalone_paths
        if standalone_paths and result["scenario"] in {"anonymous", "unprivileged_role"}:
            analyzed.update(
                verdict="CONFIRMED",
                reasons=[
                    "Debug endpoint exposed excessive sensitive data (plaintext credentials) to unprivileged or anonymous caller at "
                    + ", ".join(standalone_paths)
                    + "."
                ],
            )
        elif standalone_paths and result["scenario"] == "admin_control":
            analyzed.update(
                verdict="OBSERVATION",
                reasons=[
                    "Admin caller received plaintext credentials from debug endpoint (Excessive Data Exposure) at "
                    + ", ".join(standalone_paths)
                    + "."
                ],
            )
        else:
            analyzed.update(
                verdict="INCONCLUSIVE",
                reasons=["Debug endpoint returned 2xx without recognizable sensitive fields."],
            )
    elif result["scenario"] in {"anonymous", "invalid_token"}:
        analyzed.update(
            verdict="INCONCLUSIVE",
            reasons=["Request unexpectedly succeeded but did not meet the sensitive-data confirmation rule."],
        )
    else:
        analyzed.update(
            verdict="INCONCLUSIVE",
            reasons=["Successful response requires manual review; no sensitive owner-baseline match was found."],
        )
    return analyzed


def analyze_all(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find owner controls and use them as baselines for sibling cases."""
    baselines: dict[tuple[str, str], dict[str, Any]] = {}
    for result in results:
        if result.get("scenario") == "owner_control":
            fixture = result.get("fixture", {})
            key = (result.get("operation_id", ""), fixture.get("resource_id", ""))
            baselines[key] = result

    analyzed: list[dict[str, Any]] = []
    for result in results:
        fixture = result.get("fixture", {})
        key = (result.get("operation_id", ""), fixture.get("resource_id", ""))
        analyzed.append(analyze_result(result, baselines.get(key)))
    return analyzed
