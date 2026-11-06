from backend.app.persistence.models import Identity, Policy, Resource, ResourceType, Target
from backend.app.services.run_snapshot import snapshot_run


def test_run_snapshot_is_allowlisted_and_excludes_credentials() -> None:
    target = Target(id=1, project_id=2, base_url="http://127.0.0.1:5000", timeout_seconds=5, request_limit=50, verification_path="/me")
    resource = Resource(id=3, resource_type_id=4, external_id="book-a", owner_identity_id=5, path_parameter="id")
    policy = Policy(id=6, version=2, operation_id=7, resource_type_id=4, identity_id=8, role=None, resource_id=None, decision="DENY")

    resource_type = ResourceType(id=4, project_id=2, name="book", resource_id_pointer="/data/id", restricted_pointers=["/data/secret"])
    identity = Identity(id=5, project_id=2, display_name="Alice", role="reader", principal_pointer="/data/user", expected_principal="alice")
    snapshot = snapshot_run(target=target, resource=resource, resource_type=resource_type, policies=[policy], operation_path="/books/{id}", identities=[identity])

    assert snapshot["target"]["base_url"] == "http://127.0.0.1:5000"
    assert snapshot["target"]["verification_path"] == "/me"
    assert "ciphertext" not in repr(snapshot)
    assert "token" not in repr(snapshot).lower()
