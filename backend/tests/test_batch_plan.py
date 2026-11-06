from backend.app.persistence.models import Identity, IdentitySecret, OpenApiOperation, OperationResourceMapping, Resource, ResourceType, Target
from backend.app.services.batch_plan import BatchPlanError, build_batch_plan


def configuration(*, request_limit: int = 20):
    target = Target(id=1, project_id=1, base_url="http://127.0.0.1:5000", timeout_seconds=5, request_limit=request_limit, verification_path="/me")
    identities = [
        Identity(id=2, project_id=1, display_name="Alice", role="reader", principal_pointer="/data/name", expected_principal="alice"),
        Identity(id=3, project_id=1, display_name="Bob", role="reader", principal_pointer="/data/name", expected_principal="bob"),
    ]
    secrets = [
        IdentitySecret(identity_id=2, ciphertext="encrypted-a", key_version=1, fingerprint="a" * 64),
        IdentitySecret(identity_id=3, ciphertext="encrypted-b", key_version=1, fingerprint="b" * 64),
    ]
    operation = OpenApiOperation(id=4, project_id=1, operation_key="getBook", method="GET", path="/books/{id}", selected=True)
    resource_type = ResourceType(id=5, project_id=1, name="book", resource_id_pointer="/data/id", restricted_pointers=["/data/secret"])
    resources = [
        Resource(id=6, resource_type_id=5, external_id="book-a", owner_identity_id=2, path_parameter="id"),
        Resource(id=7, resource_type_id=5, external_id="book-b", owner_identity_id=3, path_parameter="id"),
    ]
    mapping = OperationResourceMapping(id=8, project_id=1, operation_id=4, resource_type_id=5, selected=True)
    return target, identities, secrets, [mapping], [operation], [resource_type], resources


def test_batch_plan_expands_exact_mapped_resources_and_identities() -> None:
    target, identities, secrets, mappings, operations, resource_types, resources = configuration()

    plan = build_batch_plan(
        target=target, identities=identities, identity_secrets=secrets, mappings=mappings,
        operations=operations, resource_types=resource_types, resources=resources, policies=[],
    )

    assert [item.resource.id for item in plan.targets] == [6, 7]
    assert plan.identity_verifications == 2
    assert plan.owner_baselines == 2
    assert plan.actor_case_count == 4
    assert plan.planned_attempts == 8
    assert plan.maximum_http_requests == 8
    assert plan.within_request_limit is True


def test_batch_plan_rejects_unmatched_resource_path_parameter() -> None:
    target, identities, secrets, mappings, operations, resource_types, resources = configuration()
    resources[0].path_parameter = "book_id"

    try:
        build_batch_plan(
            target=target, identities=identities, identity_secrets=secrets, mappings=mappings,
            operations=operations, resource_types=resource_types, resources=resources, policies=[],
        )
    except BatchPlanError as error:
        assert "path parameter" in str(error)
    else:
        raise AssertionError("expected incompatible resource configuration to be rejected")
