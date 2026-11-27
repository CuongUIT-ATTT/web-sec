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


def meaningful_restricted_value(value: Any) -> bool:
    """Conservative evidence: every nested leaf must be observable and nonempty."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        children = value.values() if isinstance(value, dict) else value
        return bool(value) and all(meaningful_restricted_value(child) for child in children)
    return isinstance(value, (bool, int, float))


def restricted_evidence_valid(body: Any, pointers: tuple[str, ...]) -> bool:
    try:
        return bool(pointers) and all(meaningful_restricted_value(resolve_pointer(body, pointer)) for pointer in pointers)
    except JsonPointerError:
        return False


def restricted_fields_match(owner_body: Any, actor_body: Any, pointers: tuple[str, ...]) -> bool:
    if not restricted_evidence_valid(owner_body, pointers) or not restricted_evidence_valid(actor_body, pointers):
        return False
    try:
        # JSON types matter: Python otherwise considers True == 1.
        import json
        return all(json.dumps(resolve_pointer(owner_body, pointer), sort_keys=True) ==
                   json.dumps(resolve_pointer(actor_body, pointer), sort_keys=True) for pointer in pointers)
    except JsonPointerError:
        return False


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
    if policy_decision == PolicyDecision.UNKNOWN:
        return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("policy.unknown_decision",))
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
    if not owner_control_valid or owner_body is None or not restricted_evidence_valid(owner_body, restricted_pointers):
        return Evaluation(AuthorizationConclusion.INVALID_TEST, ("evidence.owner_control_invalid",))
    try:
        resource_matches = str(resolve_pointer(observation.json_body, resource_pointer)) == requested_resource_id
    except JsonPointerError:
        resource_matches = False
    if policy_decision == PolicyDecision.DENY:
        if resource_matches and restricted_fields_match(owner_body, observation.json_body, restricted_pointers):
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


def evaluate_authorization_case(*, case, identity_confirmed, baseline_valid,
                                baseline_body, observation):
    """Evaluate a revision-backed case without manufacturing a legacy policy ID.

    Function execution requires configured result identity AND protected result
    fields equivalent to an independently authorized baseline. A denial envelope
    is considered only after checking for disclosure, including HTTP 403 bodies.
    """
    if observation.execution_status in {
        ExecutionStatus.SCOPE_BLOCKED, ExecutionStatus.REQUEST_LIMIT_REACHED, ExecutionStatus.CANCELLED,
    } and observation.status_code is None and observation.json_body is None:
        return Evaluation(AuthorizationConclusion.NOT_RUN,
            (f"execution.{observation.execution_status.lower()}",))
    contract = case.get("observation_contract") or {}
    if case["expected_decision"] == "UNKNOWN":
        return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("policy.unknown_decision",))
    if not identity_confirmed:
        return Evaluation(AuthorizationConclusion.INVALID_TEST, ("evidence.principal_mismatch",))
    if case["kind"] == "BFLA":
        if not (contract.get("result_pointer") and contract.get("result_value") is not None
                and contract.get("protected_pointers")):
            return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, ("evidence.function_result_not_configured",))
        resource_id, pointer = contract["result_value"], contract["result_pointer"]
        protected = tuple(contract["protected_pointers"])
    else:
        resource = case["resource"]
        resource_id, pointer = resource["external_id"], resource["resource_id_pointer"]
        protected = tuple(resource["restricted_pointers"])
    denial = ((contract["denial_pointer"], contract["denial_value"])
              if contract.get("denial_pointer") else None)
    result = evaluate(policy_status=PolicyResolutionStatus.RESOLVED,
        policy_decision=PolicyDecision(case["expected_decision"]),
        identity_confirmed=identity_confirmed, owner_control_valid=baseline_valid,
        requested_resource_id=str(resource_id), resource_pointer=pointer,
        restricted_pointers=protected, owner_body=baseline_body,
        observation=observation, denial_convention=denial)

    if result.conclusion == AuthorizationConclusion.NOT_EVALUATED:
        return Evaluation(AuthorizationConclusion.INSUFFICIENT_EVIDENCE, result.reason_codes)
    if (result.conclusion == AuthorizationConclusion.INSUFFICIENT_EVIDENCE and
            case["expected_decision"] == "DENY" and baseline_valid and
            observation.execution_status == ExecutionStatus.COMPLETED_RESPONSE and
            not observation.body_truncated and not observation.parse_error):
        try:
            same_resource = str(resolve_pointer(observation.json_body, pointer)) == str(resource_id)
        except JsonPointerError:
            same_resource = False
        if same_resource and restricted_evidence_valid(observation.json_body, protected):
            return Evaluation(AuthorizationConclusion.SUSPECTED_VIOLATION,
                ("evidence.protected_disclosure_differs_from_baseline",))
    return result
