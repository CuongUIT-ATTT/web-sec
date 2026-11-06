"""Deterministic policy selection that blocks ambiguous conflicting rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.app.domain.contracts import PolicyDecision, PolicyResolutionStatus


@dataclass(frozen=True)
class PolicyRule:
    id: int
    version: int
    operation_id: int
    resource_type_id: int
    identity_id: int | None
    role: str | None
    resource_id: int | None
    decision: PolicyDecision


@dataclass(frozen=True)
class PolicyResolution:
    status: PolicyResolutionStatus
    rule: PolicyRule | None


def _specificity(
    rule: PolicyRule,
    *,
    operation_id: int,
    resource_type_id: int,
    identity_id: int,
    role: str | None,
    resource_id: int,
) -> int | None:
    if rule.operation_id != operation_id or rule.resource_type_id != resource_type_id:
        return None
    if rule.identity_id is not None:
        if rule.identity_id != identity_id:
            return None
        subject_score = 4
    elif rule.role is not None:
        if rule.role != role:
            return None
        subject_score = 2
    else:
        return None
    if rule.resource_id is not None:
        if rule.resource_id != resource_id:
            return None
        return subject_score + 1
    return subject_score


def resolve_policy(
    rules: Iterable[PolicyRule],
    *,
    operation_id: int,
    resource_type_id: int,
    identity_id: int,
    role: str | None,
    resource_id: int,
) -> PolicyResolution:
    candidates = [
        (score, rule)
        for rule in rules
        if (score := _specificity(
            rule,
            operation_id=operation_id,
            resource_type_id=resource_type_id,
            identity_id=identity_id,
            role=role,
            resource_id=resource_id,
        )) is not None
    ]
    if not candidates:
        return PolicyResolution(PolicyResolutionStatus.NO_MATCH, None)
    highest = max(score for score, _ in candidates)
    best = [rule for score, rule in candidates if score == highest]
    if len({rule.decision for rule in best}) > 1:
        return PolicyResolution(PolicyResolutionStatus.UNRESOLVED_CONFLICT, None)
    return PolicyResolution(PolicyResolutionStatus.RESOLVED, sorted(best, key=lambda rule: rule.id)[0])
