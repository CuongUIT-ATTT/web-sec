"""Create redacted immutable run snapshots from durable configuration metadata."""

from __future__ import annotations

from backend.app.persistence.models import Identity, Policy, Resource, ResourceType, Target
from backend.app.services.batch_plan import BatchPlan


def _identity_snapshot(identity: Identity) -> dict[str, object]:
    return {
        "id": identity.id,
        "role": identity.role,
        "principal_pointer": identity.principal_pointer,
        "expected_principal": identity.expected_principal,
    }


def _policy_snapshot(policy: Policy) -> dict[str, object]:
    return {
        "id": policy.id,
        "version": policy.version,
        "operation_id": policy.operation_id,
        "resource_type_id": policy.resource_type_id,
        "identity_id": policy.identity_id,
        "role": policy.role,
        "resource_id": policy.resource_id,
        "decision": policy.decision,
    }


def _target_snapshot(target: Target) -> dict[str, object]:
    return {
        "id": target.id,
        "base_url": target.base_url,
        "timeout_seconds": target.timeout_seconds,
        "request_limit": target.request_limit,
        "verification_path": target.verification_path,
    }


def snapshot_batch_run(plan: BatchPlan) -> dict[str, object]:
    """Return an immutable batch plan with no tokens, ciphertext, or response data."""
    return {
        "schema_version": 2,
        "run_kind": "BATCH_ALL_SELECTED",
        "target": _target_snapshot(plan.target),
        "request_plan": {
            "identity_verifications": plan.identity_verifications,
            "owner_baselines": plan.owner_baselines,
            "actor_cases": plan.actor_case_count,
            "planned_attempts": plan.planned_attempts,
            # Kept for schema-v2 readers; it is a logical plan, not server receipt.
            "maximum_http_requests": plan.maximum_http_requests,
        },
        "identities": [_identity_snapshot(identity) for identity in plan.identities],
        "targets": [
            {
                "mapping_id": item.mapping.id,
                "operation": {"id": item.operation.id, "path": item.operation.path, "method": item.operation.method},
                "resource": {
                    "id": item.resource.id,
                    "external_id": item.resource.external_id,
                    "resource_type_id": item.resource.resource_type_id,
                    "owner_identity_id": item.resource.owner_identity_id,
                    "path_parameter": item.resource.path_parameter,
                    "resource_id_pointer": item.resource_type.resource_id_pointer,
                    "restricted_pointers": item.resource_type.restricted_pointers,
                },
                "policies": [_policy_snapshot(policy) for policy in item.policies],
            }
            for item in plan.targets
        ],
    }




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
        "target": _target_snapshot(target),
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
        "identities": [_identity_snapshot(identity) for identity in identities],
        "policies": [_policy_snapshot(policy) for policy in policies],
    }
