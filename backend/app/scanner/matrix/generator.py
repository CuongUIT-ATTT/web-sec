"""Generate configured read-only owner and cross-identity cases without enumeration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.app.domain.contracts import PolicyResolutionStatus
from backend.app.scanner.classification.policy import PolicyResolution


@dataclass(frozen=True)
class MatrixCase:
    case_key: str
    control_type: str
    actor_identity_id: int
    resource_id: int
    policy_status: PolicyResolutionStatus
    warnings: tuple[str, ...]


def generate_cases(
    *,
    resource_id: int,
    owner_identity_id: int,
    actor_identity_ids: Iterable[int],
    resolutions: dict[int, PolicyResolution],
    verified_identity_ids: set[int],
) -> list[MatrixCase]:
    """Materialize only configured identities/resources; verification affects warnings, not generation."""
    cases: list[MatrixCase] = []
    for actor_identity_id in sorted(set(actor_identity_ids)):
        resolution = resolutions[actor_identity_id]
        warnings: list[str] = []
        if actor_identity_id not in verified_identity_ids:
            warnings.append("identity.unverified_precheck")
        if resolution.status == PolicyResolutionStatus.UNRESOLVED_CONFLICT:
            warnings.append("policy.unresolved_conflict")
        if resolution.status == PolicyResolutionStatus.NO_MATCH:
            warnings.append("policy.no_resolved_rule")
        cases.append(MatrixCase(
            case_key=f"resource:{resource_id}:actor:{actor_identity_id}",
            control_type="OWNER_CONTROL" if actor_identity_id == owner_identity_id else "CROSS_IDENTITY",
            actor_identity_id=actor_identity_id,
            resource_id=resource_id,
            policy_status=resolution.status,
            warnings=tuple(warnings),
        ))
    return cases
