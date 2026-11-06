"""Persist confirmed findings by stable fingerprint and retain each run case as reproduction."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.domain.contracts import AuthorizationConclusion
from backend.app.persistence.models import Finding, FindingReproduction, RunResult
from backend.app.scanner.classification.findings import FindingKey
from backend.app.scanner.classification.policy import PolicyRule


def _load_or_create_finding(session: Session, *, project_id: int, fingerprint: str, values: dict[str, object]) -> Finding:
    existing = session.scalar(select(Finding).where(Finding.project_id == project_id, Finding.fingerprint == fingerprint))
    if existing is not None:
        return existing
    try:
        with session.begin_nested():
            finding = Finding(project_id=project_id, fingerprint=fingerprint, **values)
            session.add(finding)
            session.flush()
        return finding
    except IntegrityError:
        finding = session.scalar(select(Finding).where(Finding.project_id == project_id, Finding.fingerprint == fingerprint))
        if finding is None:
            raise
        return finding


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
    """Create exactly one normalized finding and reproduction for this immutable result."""
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
    finding = _load_or_create_finding(
        session,
        project_id=project_id,
        fingerprint=fingerprint,
        values={
            "conclusion": AuthorizationConclusion.CONFIRMED_VIOLATION,
            "operation_method": "GET",
            "operation_path": operation_path,
            "policy_id": policy.id,
            "policy_version": policy.version,
            "resource_type_id": policy.resource_type_id,
            "resource_pointer": resource_pointer,
            "restricted_pointers": sorted(restricted_pointers),
        },
    )
    existing = session.scalar(select(FindingReproduction).where(
        FindingReproduction.finding_id == finding.id,
        FindingReproduction.run_result_id == run_result.id,
    ))
    if existing is None:
        try:
            with session.begin_nested():
                session.add(FindingReproduction(
                    finding_id=finding.id,
                    run_result_id=run_result.id,
                    actor_identity_id=actor_identity_id,
                    resource_id=resource_id,
                ))
                session.flush()
        except IntegrityError:
            # A concurrent worker created the same unique reproduction; preserve it.
            pass
    return finding
