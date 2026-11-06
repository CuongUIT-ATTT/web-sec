from backend.app.domain.contracts import AuthorizationConclusion, ExecutionStatus, PolicyDecision, PolicyResolutionStatus
from backend.app.scanner.classification.evaluator import Observation, evaluate


def assess(**overrides):
    values = {
        "policy_status": PolicyResolutionStatus.RESOLVED,
        "policy_decision": PolicyDecision.DENY,
        "identity_confirmed": True,
        "owner_control_valid": True,
        "requested_resource_id": "book-2",
        "resource_pointer": "/data/id",
        "restricted_pointers": ("/data/secret",),
        "owner_body": {"data": {"id": "book-2", "secret": "owner-secret"}},
        "observation": Observation(ExecutionStatus.COMPLETED_RESPONSE, 200, {"data": {"id": "book-2", "secret": "owner-secret"}}),
    }
    values.update(overrides)
    return evaluate(**values)


def test_confirms_deny_violation_from_identity_owner_resource_and_restricted_evidence() -> None:
    result = assess()

    assert result.conclusion == AuthorizationConclusion.CONFIRMED_VIOLATION


def test_403_body_leakage_can_still_confirm_violation() -> None:
    result = assess(observation=Observation(ExecutionStatus.COMPLETED_RESPONSE, 403, {"data": {"id": "book-2", "secret": "owner-secret"}}))

    assert result.conclusion == AuthorizationConclusion.CONFIRMED_VIOLATION


def test_200_denial_needs_explicit_supported_convention() -> None:
    observation = Observation(ExecutionStatus.COMPLETED_RESPONSE, 200, {"data": {"id": "book-2"}, "error": {"code": "DENIED"}})

    missing_convention = assess(observation=observation)
    configured_convention = assess(observation=observation, denial_convention=("/error/code", "DENIED"))

    assert missing_convention.conclusion == AuthorizationConclusion.INSUFFICIENT_EVIDENCE
    assert missing_convention.reason_codes == ("auth.unsupported_denial_convention",)
    assert configured_convention.conclusion == AuthorizationConclusion.POLICY_CONSISTENT_CASE


def test_truncated_and_invalid_json_are_not_policy_consistent() -> None:
    truncated = assess(observation=Observation(ExecutionStatus.COMPLETED_RESPONSE, 403, None, body_truncated=True))
    invalid_json = assess(observation=Observation(ExecutionStatus.COMPLETED_RESPONSE, 403, None, parse_error=True))

    assert truncated.conclusion == AuthorizationConclusion.NOT_EVALUATED
    assert truncated.reason_codes == ("evidence.body_truncated",)
    assert invalid_json.conclusion == AuthorizationConclusion.NOT_EVALUATED
    assert invalid_json.reason_codes == ("evidence.json_parse_error",)


def test_policy_conflict_and_principal_mismatch_are_separate_outcomes() -> None:
    conflict = assess(policy_status=PolicyResolutionStatus.UNRESOLVED_CONFLICT)
    mismatch = assess(identity_confirmed=False)

    assert conflict.conclusion == AuthorizationConclusion.BLOCKED_POLICY_CONFLICT
    assert mismatch.conclusion == AuthorizationConclusion.INVALID_TEST
