"""Allowlisted response/export views that cannot expose stored credentials or bodies."""

from __future__ import annotations

from backend.app.persistence.models import Identity, RunResult


def serialize_identity(identity: Identity) -> dict[str, object]:
    return {
        "id": identity.id,
        "display_name": identity.display_name,
        "role": identity.role,
        "principal_pointer": identity.principal_pointer,
        "expected_principal": identity.expected_principal,
        "has_secret": identity.secret is not None,
        "created_at": identity.created_at.isoformat() if identity.created_at else None,
    }


def serialize_result(result: RunResult) -> dict[str, object]:
    return {
        "id": result.id,
        "case_key": result.case_key,
        "execution_status": result.execution_status,
        "authorization_conclusion": result.authorization_conclusion,
        "reason_codes": result.reason_codes,
        "http_status": result.http_status,
        "response_metadata": result.response_metadata,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }
