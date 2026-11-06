"""Create redacted immutable run snapshots from durable configuration metadata."""

from __future__ import annotations

from backend.app.persistence.models import Identity, Policy, Resource, ResourceType, Target


def snapshot_run(
    *,
    target: Target,
    resource: Resource,
    resource_type: ResourceType,
    policies: list[Policy],
    operation_path: str,
    identities: list[Identity],
) -> dict[str, object]:
    """Return metadata needed for audit without credential ciphertext or response bodies."""
    return {
        "target": {
            "id": target.id,
            "base_url": target.base_url,
            "timeout_seconds": target.timeout_seconds,
            "request_limit": target.request_limit,
            "verification_path": target.verification_path,
        },
        "operation": {"path": operation_path, "method": "GET"},
        "resource": {
            "id": resource.id,
            "external_id": resource.external_id,
            "resource_type_id": resource.resource_type_id,
            "owner_identity_id": resource.owner_identity_id,
            "path_parameter": resource.path_parameter,
            "resource_id_pointer": resource_type.resource_id_pointer,
            "restricted_pointers": resource_type.restricted_pointers,
        },
        "identities": [
            {
                "id": identity.id,
                "role": identity.role,
                "principal_pointer": identity.principal_pointer,
                "expected_principal": identity.expected_principal,
            }
            for identity in identities
        ],
        "policies": [
            {
                "id": policy.id,
                "version": policy.version,
                "operation_id": policy.operation_id,
                "resource_type_id": policy.resource_type_id,
                "identity_id": policy.identity_id,
                "role": policy.role,
                "resource_id": policy.resource_id,
                "decision": policy.decision,
            }
            for policy in policies
        ],
    }
