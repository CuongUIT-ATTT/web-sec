"""Parse a local OpenAPI document into a reviewable endpoint inventory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
FORBIDDEN_PATHS = {"/createdb"}


def load_spec(path: str | Path) -> dict[str, Any]:
    """Load an OpenAPI JSON document and validate its minimum structure."""
    with Path(path).open(encoding="utf-8") as handle:
        spec = json.load(handle)
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        raise ValueError("OpenAPI document must contain an object-valued 'paths' field.")
    return spec


def _path_parameters(parameters: list[Any]) -> list[str]:
    names: list[str] = []
    for parameter in parameters:
        if not isinstance(parameter, dict) or parameter.get("in") != "path":
            continue
        name = parameter.get("name")
        if isinstance(name, str) and name not in names:
            names.append(name)
    return names


def _requires_auth(detail: dict[str, Any], spec_security: Any) -> bool:
    security = detail.get("security", spec_security)
    return isinstance(security, list) and bool(security)


def _is_privileged(path: str, detail: dict[str, Any]) -> bool:
    searchable = " ".join(
        [
            path,
            str(detail.get("operationId", "")),
            str(detail.get("summary", "")),
            str(detail.get("description", "")),
            " ".join(str(tag) for tag in detail.get("tags", [])),
        ]
    ).lower()
    return any(keyword in searchable for keyword in ("admin", "privilege", "role", "internal"))


def extract_endpoints(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract OpenAPI operations and conservative test-candidate metadata."""
    endpoints: list[dict[str, Any]] = []
    global_security = spec.get("security")

    for path, path_item in spec["paths"].items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        shared_parameters = path_item.get("parameters", [])
        if not isinstance(shared_parameters, list):
            shared_parameters = []

        for method, detail in path_item.items():
            normalized_method = method.upper()
            if normalized_method not in SUPPORTED_METHODS or not isinstance(detail, dict):
                continue
            operation_parameters = detail.get("parameters", [])
            if not isinstance(operation_parameters, list):
                operation_parameters = []
            path_params = _path_parameters([*shared_parameters, *operation_parameters])
            requires_auth = _requires_auth(detail, global_security)
            state_changing = normalized_method not in SAFE_METHODS
            privileged = _is_privileged(path, detail)
            object_level = bool(path_params)

            endpoint = {
                "operation_id": detail.get("operationId") or f"{normalized_method}:{path}",
                "path": path,
                "method": normalized_method,
                "path_params": path_params,
                "tags": [str(tag) for tag in detail.get("tags", [])],
                "requires_auth": requires_auth,
                "declared_responses": sorted(str(code) for code in detail.get("responses", {})),
                "has_request_body": "requestBody" in detail,
                "state_changing": state_changing,
                "forbidden": path in FORBIDDEN_PATHS,
                "is_bola_candidate": object_level and not state_changing,
                "is_bfla_candidate": privileged,
                "public_object_read": object_level and not requires_auth and not state_changing,
                "execution_note": (
                    "Never execute: it resets the lab database."
                    if path in FORBIDDEN_PATHS
                    else "Disabled by default because it changes state."
                    if state_changing
                    else "Read-only operation eligible for fixture-backed tests."
                ),
            }
            endpoints.append(endpoint)

    return sorted(endpoints, key=lambda item: (item["path"], item["method"]))
