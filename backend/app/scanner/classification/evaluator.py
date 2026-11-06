"""Evidence-first authorization evaluator independent from HTTP transport outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.domain.contracts import AuthorizationConclusion, ExecutionStatus, PolicyDecision, PolicyResolutionStatus
from backend.app.scanner.classification.json_pointer import JsonPointerError, resolve_pointer


@dataclass(frozen=True)
class Observation:
    execution_status: ExecutionStatus
    status_code: int | None
    json_body: Any | None
    body_truncated: bool = False
    parse_error: bool = False


@dataclass(frozen=True)
class Evaluation:
    conclusion: AuthorizationConclusion
    reason_codes: tuple[str, ...]


def evaluate(
    *,
    policy_status: PolicyResolutionStatus,
    policy_decision: PolicyDecision | None,
    identity_confirmed: bool,
    owner_control_valid: bool,
    requested_resource_id: str,
    resource_pointer: str,
    restricted_pointers: tuple[str, ...],
    owner_body: Any | None,
    observation: Observation,
    denial_convention: tuple[str, str] | None = None,
) -> Evaluation:
    if policy_status == PolicyResolutionStatus.UNRESOLVED_CONFLICT:
        return Evaluation(AuthorizationConclusion.BLOCKED_POLICY_CONFLICT, ("policy.unresolved_conflict",))
    if policy_status == PolicyResolutionStatus.NO_MATCH or policy_decision is None:
        return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("policy.no_resolved_rule",))
    if observation.body_truncated or observation.execution_status == ExecutionStatus.BODY_TRUNCATED:
        return Evaluation(AuthorizationConclusion.NOT_EVALUATED, ("evidence.body_truncated",))
    if observation.parse_error or observation.execution_status == ExecutionStatus.JSON_PARSE_ERROR:
        return Evaluation(AuthorizationConclusion.NOT_EVALUATED, ("evidence.json_parse_error",))
    if observation.execution_status != ExecutionStatus.COMPLETED_RESPONSE:
        return Evaluation(AuthorizationConclusion.NOT_EVALUATED, (f"execution.{observation.execution_status.lower()}",))
    if observation.json_body is None:
        return Evaluation(AuthorizationConclusion.NOT_EVALUATED, ("evidence.json_unobservable",))
    if not identity_confirmed:
        return Evaluation(AuthorizationConclusion.INVALID_TEST, ("evidence.principal_mismatch",))
    if not owner_control_valid or owner_body is None:
        return Evaluation(AuthorizationConclusion.INVALID_TEST, ("evidence.owner_control_invalid",))
    try:
        resource_matches = str(resolve_pointer(observation.json_body, resource_pointer)) == requested_resource_id
    except JsonPointerError:
        resource_matches = False
    if policy_decision == PolicyDecision.DENY:
        matches = []
        for pointer in restricted_pointers:
            try:
                matches.append(resolve_pointer(observation.json_body, pointer) == resolve_pointer(owner_body, pointer))
            except JsonPointerError:
                matches.append(False)
        if resource_matches and matches and all(matches):
            return Evaluation(AuthorizationConclusion.CONFIRMED_VIOLATION, ("evidence.restricted_fields_match_owner",))
        if denial_convention:
            pointer, expected = denial_convention
            try:
                if str(resolve_pointer(observation.json_body, pointer)) == expected:
                    return Evaluation(AuthorizationConclusion.POLICY_CONSISTENT_CASE, ("auth.supported_denial_convention",))
            except JsonPointerError:
                pass
        if observation.status_code == 200:
            return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("auth.unsupported_denial_convention",))
        if not resource_matches:
            return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("evidence.response_resource_unobservable",))
        return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("evidence.no_supported_denial_evidence",))
    if not resource_matches:
        return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("evidence.response_resource_mismatch",))
    return Evaluation(AuthorizationConclusion.POLICY_CONSISTENT_CASE, ("policy.allow_observed",))
