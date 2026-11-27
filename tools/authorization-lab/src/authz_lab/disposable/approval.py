"""Local operator acknowledgement, NOT authenticated signatures or remote authority.

The independently supplied digest pins the operator-reviewed record. A malicious
operator or writer controlling both inputs remains inside the local trust boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

from .manifest import BflaManifestError, load_manifest, manifest_path, validate_run_directory

current_budget = ContextVar("disposable_approval_budget", default=None)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class RequestBudget:
    def __init__(self, manifest, stage):
        self.scope = manifest["execution_scopes"][stage]
        self.run_id = manifest["run_id"]
        self.used = 0

    def consume(self, path, method, payload):
        fields = sorted(payload) if isinstance(payload, dict) else []
        if payload is not None and not isinstance(payload, dict):
            raise BflaManifestError("Invalid approved payload shape.")
        operation = {"method": method, "path": path, "payload_fields": fields}
        if operation not in self.scope["operations"]:
            raise BflaManifestError("Request outside approved stage scope.")
        if method == "POST":
            allowed = {f"bfla-{self.run_id}-victim", f"bfla-{self.run_id}-escalated"}
            if payload.get("username") not in allowed:
                raise BflaManifestError("Request principal outside approved fixture.")
            if path.endswith("register") and (payload["username"] != f"bfla-{self.run_id}-escalated" or payload.get("admin") is not True):
                raise BflaManifestError("Registration outside approved fixture.")
        if self.used >= self.scope["request_cap"]:
            raise BflaManifestError("Approved request budget exhausted.")
        self.used += 1


def consume_approval(manifest, stage, run_dir, approval, approval_digest, *, now=None):
    """Validate all bindings before creating an exclusive persistent stage claim.

    A claim is deliberately retained on failure; retry needs a new run. This is
    one-use acknowledgement, not a complete lifecycle/crash recovery mechanism.
    """
    if manifest.get("schema_version") != 2 or approval is None:
        raise BflaManifestError("Explicit v2 operator approval is required.")
    source = Path(approval)
    if source.is_symlink() or not source.is_file():
        raise BflaManifestError("Approval must be a regular local file.")
    record = json.loads(source.read_text(encoding="utf-8"))
    keys = {"schema_version", "run_id", "stage", "manifest_digest", "scope_digest", "issued_at", "expires_at", "nonce", "operator", "provenance"}
    if not isinstance(record, dict) or set(record) != keys:
        raise BflaManifestError("Malformed operator approval.")
    if not isinstance(approval_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", approval_digest) or digest(record) != approval_digest:
        raise BflaManifestError("Approval digest mismatch.")
    timestamp = time.time() if now is None else now
    issued, expires = record["issued_at"], record["expires_at"]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in (issued, expires)) or not issued <= timestamp < expires or expires - issued > 3600:
        raise BflaManifestError("Approval is stale or has an invalid validity window.")
    if (type(record["schema_version"]) is not int or record["schema_version"] != 1
        or record["run_id"] != manifest["run_id"] or record["stage"] != stage
        or record["manifest_digest"] != digest(manifest)
        or record["scope_digest"] != digest(manifest["execution_scopes"][stage])
        or record["provenance"] != "local-operator-acknowledgement"
        or not isinstance(record["operator"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", record["operator"])
        or not isinstance(record["nonce"], str) or not re.fullmatch(r"[0-9a-f]{32}", record["nonce"])):
        raise BflaManifestError("Approval binding or provenance mismatch.")
    directory = validate_run_directory(run_dir, manifest["run_id"])
    if not directory.is_dir():
        raise BflaManifestError("Prepared run directory is required.")
    claim = directory / f".{stage}-approval-used"
    descriptor = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(approval_digest + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return RequestBudget(manifest, stage)


def approved_stage(stage):
    def decorate(function):
        @wraps(function)
        def guarded(run_id, project, run_dir, results_root="results/bfla-disposable", *, approval=None, approval_digest=None):
            manifest = load_manifest(manifest_path(run_id, results_root))
            if manifest["target"]["compose_project"] != project:
                raise BflaManifestError("Approval project mismatch.")
            budget = consume_approval(manifest, stage, run_dir, approval, approval_digest)
            context = current_budget.set(budget)
            try:
                return function(run_id, project, run_dir, results_root)
            finally:
                current_budget.reset(context)
        return guarded
    return decorate
