"""Strict DTOs and HMAC helpers for the operator-side read-only lab bridge."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.domain.contracts import ExternalLabJobKind, ExternalLabJobStatus

PROTOCOL_VERSION = 1
MAX_SUMMARY_KEYS = frozenset({
    "case_count", "outcome_counts", "preflight_passed", "redaction_verified",
    "elapsed_ms", "target_label",
})
BRIDGE_EVENT_AUDIENCE = "bridge-to-web"
WEB_REQUEST_AUDIENCE = "web-to-bridge"


class BridgeProtocolError(ValueError):
    """Raised when bridge protocol input is malformed, expired, or unauthenticated."""


class BridgeJobSubmission(BaseModel):
    """Parameterless fixed-workflow command accepted by the bridge."""

    model_config = ConfigDict(extra="forbid")

    public_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f-]{27}$")
    job_kind: ExternalLabJobKind
    protocol_version: int = Field(ge=PROTOCOL_VERSION, le=PROTOCOL_VERSION)


class BridgeJobEvent(BaseModel):
    """Redacted bridge event; raw artifacts and output are never accepted."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    status: ExternalLabJobStatus
    started_at: int | None = Field(default=None, ge=0)
    finished_at: int | None = Field(default=None, ge=0)
    failure_code: str | None = Field(default=None, pattern=r"^[A-Z_]{1,64}$")
    summary: dict[str, Any] = Field(default_factory=dict)
    artifact_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) - MAX_SUMMARY_KEYS:
            raise ValueError("Bridge summary contains a non-allowlisted field.")
        if value.get("target_label") not in (None, "LOCAL_VAMPI_READ_ONLY"):
            raise ValueError("Bridge summary target label is invalid.")
        if "case_count" in value and (not isinstance(value["case_count"], int) or not 0 <= value["case_count"] <= 10000):
            raise ValueError("Bridge summary case count is invalid.")
        if "elapsed_ms" in value and (not isinstance(value["elapsed_ms"], (int, float)) or not 0 <= value["elapsed_ms"] <= 3_600_000):
            raise ValueError("Bridge summary elapsed time is invalid.")
        if "preflight_passed" in value and not isinstance(value["preflight_passed"], bool):
            raise ValueError("Bridge preflight flag is invalid.")
        if "redaction_verified" in value and not isinstance(value["redaction_verified"], bool):
            raise ValueError("Bridge redaction flag is invalid.")
        counts = value.get("outcome_counts")
        if counts is not None and (
            not isinstance(counts, dict)
            or any(not isinstance(key, str) or not isinstance(count, int) or count < 0 for key, count in counts.items())
        ):
            raise ValueError("Bridge outcome counts are invalid.")
        return value


@dataclass(frozen=True)
class SignedHeaders:
    timestamp: str
    nonce: str
    audience: str
    signature: str


def canonical_signature(secret: str, *, method: str, path: str, body: bytes, timestamp: str, nonce: str, audience: str) -> str:
    body_digest = hashlib.sha256(body).hexdigest()
    message = "\n".join((method.upper(), path, body_digest, timestamp, nonce, audience)).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def signed_headers(secret: str, *, method: str, path: str, payload: dict[str, Any], audience: str) -> tuple[bytes, SignedHeaders]:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    return body, SignedHeaders(
        timestamp=timestamp,
        nonce=nonce,
        audience=audience,
        signature=canonical_signature(secret, method=method, path=path, body=body, timestamp=timestamp, nonce=nonce, audience=audience),
    )


def verify_signed_request(
    secret: str,
    *,
    method: str,
    path: str,
    body: bytes,
    timestamp: str | None,
    nonce: str | None,
    audience: str | None,
    signature: str | None,
    expected_audience: str,
    max_skew_seconds: int,
) -> str:
    if not all((timestamp, nonce, audience, signature)) or audience != expected_audience:
        raise BridgeProtocolError("Bridge authentication headers are invalid.")
    if not nonce or len(nonce) > 128:
        raise BridgeProtocolError("Bridge nonce is invalid.")
    try:
        timestamp_value = int(timestamp)
    except (TypeError, ValueError) as error:
        raise BridgeProtocolError("Bridge timestamp is invalid.") from error
    if abs(int(time.time()) - timestamp_value) > max_skew_seconds:
        raise BridgeProtocolError("Bridge request timestamp expired.")
    expected = canonical_signature(secret, method=method, path=path, body=body, timestamp=timestamp, nonce=nonce, audience=audience)
    if not hmac.compare_digest(expected, signature):
        raise BridgeProtocolError("Bridge request signature is invalid.")
    return hashlib.sha256(f"{audience}:{nonce}".encode("utf-8")).hexdigest()
