from backend.app.domain.contracts import AuthorizationConclusion
from backend.app.scanner.classification.findings import FindingKey


def test_reverse_actor_directions_share_one_non_sensitive_finding_group() -> None:
    common = dict(
        project_id=1,
        method="GET",
        path="/books/{id}",
        policy_id=4,
        policy_version=2,
        resource_type_id=3,
        resource_pointer="/data/id",
        restricted_pointers=("/data/secret",),
        conclusion=AuthorizationConclusion.CONFIRMED_VIOLATION,
    )
    alice_to_bob = FindingKey(**common)
    bob_to_alice = FindingKey(**common)

    assert alice_to_bob.fingerprint() == bob_to_alice.fingerprint()
    assert "secret" not in alice_to_bob.fingerprint()
