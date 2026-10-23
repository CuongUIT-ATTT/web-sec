"""Validate the narrow, local-only request manifest used for ZAP assessment."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from week2.request_runner import ALLOWED_BASE_URL

from .common import read_json

SAFE_METHOD = "GET"
FORBIDDEN_PATHS = {"/createdb"}
REQUIRED_TOP_LEVEL_FIELDS = {"schema_version", "assessment_id", "target", "allowed_requests", "prohibitions"}


class ZapAllowlistError(ValueError):
    """Raised when a ZAP assessment manifest would exceed the safe local scope."""


def _validate_target(target: Any) -> str:
    if target != ALLOWED_BASE_URL:
        raise ZapAllowlistError(f"ZAP target must be exactly {ALLOWED_BASE_URL}.")
    return target


def _validate_path(path: Any) -> str:
    if not isinstance(path, str):
        raise ZapAllowlistError("Each allowed ZAP path must be a string.")
    parsed = urlsplit(path)
    if (
        not path.startswith("/")
        or path in FORBIDDEN_PATHS
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise ZapAllowlistError("Allowed ZAP paths must be local absolute paths without query or fragment.")
    return path


def load_zap_allowlist(path: str | Path) -> dict[str, Any]:
    """Load a reviewed GET-only ZAP manifest without adding scan capability."""
    manifest = read_json(path)
    if not isinstance(manifest, dict) or not REQUIRED_TOP_LEVEL_FIELDS <= manifest.keys():
        raise ZapAllowlistError("ZAP manifest is missing required top-level fields.")
    if manifest["schema_version"] not in {1, 2}:
        raise ZapAllowlistError("Unsupported ZAP manifest schema version.")
    if not isinstance(manifest["assessment_id"], str) or not manifest["assessment_id"]:
        raise ZapAllowlistError("ZAP manifest assessment_id must be non-empty.")
    _validate_target(manifest["target"])

    requests = manifest["allowed_requests"]
    if not isinstance(requests, list) or not requests:
        raise ZapAllowlistError("ZAP manifest must contain at least one allowed request.")

    approved: set[tuple[str, str]] = set()
    for request in requests:
        if not isinstance(request, dict):
            raise ZapAllowlistError("Each ZAP allowed request must be an object.")
        method = request.get("method")
        path_value = _validate_path(request.get("path"))
        if method != SAFE_METHOD:
            raise ZapAllowlistError("ZAP manifest permits GET requests only.")
        key = (method, path_value)
        if key in approved:
            raise ZapAllowlistError("ZAP manifest contains a duplicate allowed request.")
        approved.add(key)

    prohibitions = manifest["prohibitions"]
    required_prohibitions = {"/createdb", "POST", "PUT", "PATCH", "DELETE"}
    if not isinstance(prohibitions, list) or not required_prohibitions <= set(prohibitions):
        raise ZapAllowlistError("ZAP manifest must explicitly prohibit reset and state-changing methods.")
    return manifest


def approved_request_pairs(manifest: dict[str, Any]) -> set[tuple[str, str]]:
    """Return the exact method/path pairs that may enter a reviewed ZAP context."""
    return {(request["method"], request["path"]) for request in manifest["allowed_requests"]}
