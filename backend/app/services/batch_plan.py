"""Pure planning for explicitly configured, read-only batch authorization runs."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.persistence.models import Identity, IdentitySecret, OpenApiOperation, OperationResourceMapping, Policy, Resource, ResourceType, Target


class BatchPlanError(ValueError):
    """Raised when stored configuration cannot safely define a complete batch."""


@dataclass(frozen=True)
class BatchTarget:
    mapping: OperationResourceMapping
    operation: OpenApiOperation
    resource_type: ResourceType
    resource: Resource
    policies: tuple[Policy, ...]


@dataclass(frozen=True)
class BatchPlan:
    target: Target
    identities: tuple[Identity, ...]
    targets: tuple[BatchTarget, ...]
    identity_verifications: int
    owner_baselines: int
    actor_case_count: int

    @property
    def planned_attempts(self) -> int:
        """The immutable logical budget: I + C + (I × C)."""
        return self.identity_verifications + self.owner_baselines + self.actor_case_count

    @property
    def maximum_http_requests(self) -> int:
        """Temporary schema-v2 compatibility alias for planned attempts."""
        return self.planned_attempts

    @property
    def within_request_limit(self) -> bool:
        return self.planned_attempts <= self.target.request_limit


def build_batch_plan(
    *,
    target: Target,
    identities: list[Identity],
    identity_secrets: list[IdentitySecret],
    mappings: list[OperationResourceMapping],
    operations: list[OpenApiOperation],
    resource_types: list[ResourceType],
    resources: list[Resource],
    policies: list[Policy],
) -> BatchPlan:
    """Expand only enabled stored mappings and exact configured resources.

    The planner is deliberately network-free. It never constructs identifiers beyond
    the configured resource rows and makes the request budget explicit before a run
    can be queued.
    """
    ordered_identities = tuple(sorted(identities, key=lambda item: item.id))
    if not ordered_identities:
        raise BatchPlanError("Cần ít nhất một danh tính đã cấu hình để chạy batch.")
    secret_ids = {secret.identity_id for secret in identity_secrets}
    if any(identity.id not in secret_ids for identity in ordered_identities):
        raise BatchPlanError("Mọi danh tính trong batch phải có bearer token write-only.")

    operations_by_id = {operation.id: operation for operation in operations}
    resource_types_by_id = {resource_type.id: resource_type for resource_type in resource_types}
    identities_by_id = {identity.id: identity for identity in ordered_identities}
    resources_by_type: dict[int, list[Resource]] = {}
    for resource in resources:
        resources_by_type.setdefault(resource.resource_type_id, []).append(resource)

    targets: list[BatchTarget] = []
    for mapping in sorted((item for item in mappings if item.selected), key=lambda item: (item.operation_id, item.resource_type_id, item.id)):
        operation = operations_by_id.get(mapping.operation_id)
        resource_type = resource_types_by_id.get(mapping.resource_type_id)
        if operation is None or resource_type is None:
            raise BatchPlanError("Mapping batch tham chiếu cấu hình không thuộc dự án.")
        if not operation.selected or operation.method != "GET":
            raise BatchPlanError("Mapping batch chỉ cho phép operation GET đang được chọn.")
        for resource in sorted(resources_by_type.get(resource_type.id, []), key=lambda item: item.id):
            if resource.owner_identity_id not in identities_by_id:
                raise BatchPlanError("Owner resource phải là danh tính đã cấu hình của dự án.")
            if "{" + resource.path_parameter + "}" not in operation.path:
                raise BatchPlanError("path parameter resource không tương thích với operation đã mapping.")
            applicable = tuple(sorted(
                (policy for policy in policies if policy.operation_id == operation.id and policy.resource_type_id == resource_type.id),
                key=lambda item: item.id,
            ))
            targets.append(BatchTarget(mapping, operation, resource_type, resource, applicable))

    if not targets:
        raise BatchPlanError("Chưa có resource thuộc mapping GET đã bật để chạy batch.")

    return BatchPlan(
        target=target,
        identities=ordered_identities,
        targets=tuple(targets),
        identity_verifications=len(ordered_identities),
        owner_baselines=len(targets),
        actor_case_count=len(ordered_identities) * len(targets),
    )
