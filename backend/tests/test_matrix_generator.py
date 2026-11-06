from backend.app.domain.contracts import PolicyResolutionStatus
from backend.app.scanner.classification.policy import PolicyResolution
from backend.app.scanner.matrix.generator import generate_cases


def test_matrix_materializes_before_identity_verification_with_warning() -> None:
    cases = generate_cases(
        resource_id=7,
        owner_identity_id=1,
        actor_identity_ids=[1, 2],
        resolutions={
            1: PolicyResolution(PolicyResolutionStatus.RESOLVED, None),
            2: PolicyResolution(PolicyResolutionStatus.UNRESOLVED_CONFLICT, None),
        },
        verified_identity_ids=set(),
    )

    assert [case.control_type for case in cases] == ["OWNER_CONTROL", "CROSS_IDENTITY"]
    assert all("identity.unverified_precheck" in case.warnings for case in cases)
    assert "policy.unresolved_conflict" in cases[1].warnings
