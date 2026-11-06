"""Persist confirmed findings by stable fingerprint and retain each run case as reproduction."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain.contracts import AuthorizationConclusion
from backend.app.persistence.models import Finding, FindingReproduction, RunResult
from backend.app.scanner.classification.findings import FindingKey
from backend.app.scanner.classification.policy import PolicyRule


def record_confirmed_reproduction(
    session: Session,
    *,
    project_id: int,
    run_result: RunResult,
    actor_identity_id: int,
    resource_id: int,
    operation_path: str,
    resource_pointer: str,
    restricted_pointers: tuple[str, ...],
    policy: PolicyRule,
) -> Finding:
    """Create one group per stable signal, never per sensitive resource value or direction."""
    key = FindingKey(
        project_id=project_id,
        method="GET",
        path=operation_path,
        policy_id=policy.id,
        policy_version=policy.version,
        resource_type_id=policy.resource_type_id,
        resource_pointer=resource_pointer,
        restricted_pointers=restricted_pointers,
        conclusion=AuthorizationConclusion.CONFIRMED_VIOLATION,
    )
    fingerprint = key.fingerprint()
    finding = session.scalar(select(Finding).where(Finding.project_id == project_id, Finding.fingerprint == fingerprint))
    if finding is None:
        finding = Finding(
            project_id=project_id,
            fingerprint=fingerprint,
            conclusion=AuthorizationConclusion.CONFIRMED_VIOLATION,
            operation_method="GET",
            operation_path=operation_path,
            policy_id=policy.id,
            policy_version=policy.version,
            resource_type_id=policy.resource_type_id,
            resource_pointer=resource_pointer,
            restricted_pointers=sorted(restricted_pointers),
        )
        session.add(finding)
        session.flush()
    session.add(FindingReproduction(
        finding_id=finding.id,
        run_result_id=run_result.id,
        actor_identity_id=actor_identity_id,
        resource_id=resource_id,
    ))
    return finding
