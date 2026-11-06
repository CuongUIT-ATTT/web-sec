from backend.app.domain.contracts import PolicyDecision, PolicyResolutionStatus
from backend.app.scanner.classification.policy import PolicyRule, resolve_policy


def rule(identifier: int, decision: PolicyDecision, *, identity_id: int | None = None, role: str | None = None, resource_id: int | None = None) -> PolicyRule:
    return PolicyRule(identifier, 1, 1, 1, identity_id, role, resource_id, decision)


def resolve(rules: list[PolicyRule]):
    return resolve_policy(rules, operation_id=1, resource_type_id=1, identity_id=2, role="reader", resource_id=9)


def test_identity_resource_rule_has_highest_specificity() -> None:
    resolution = resolve([
        rule(1, PolicyDecision.DENY, role="reader"),
        rule(2, PolicyDecision.ALLOW, identity_id=2),
        rule(3, PolicyDecision.DENY, identity_id=2, resource_id=9),
    ])

    assert resolution.status == PolicyResolutionStatus.RESOLVED
    assert resolution.rule and resolution.rule.id == 3


def test_conflicting_same_specificity_blocks_evaluation() -> None:
    resolution = resolve([
        rule(1, PolicyDecision.DENY, identity_id=2),
        rule(2, PolicyDecision.ALLOW, identity_id=2),
    ])

    assert resolution.status == PolicyResolutionStatus.UNRESOLVED_CONFLICT
    assert resolution.rule is None


def test_unrelated_operation_does_not_match() -> None:
    resolution = resolve([PolicyRule(1, 1, 2, 1, 2, None, None, PolicyDecision.DENY)])

    assert resolution.status == PolicyResolutionStatus.NO_MATCH
