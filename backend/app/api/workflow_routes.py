"""Vertical-slice workflow API: OpenAPI inventory, resources, policies, matrix, and run snapshots."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.routes import get_session
from backend.app.api.workflow_schemas import (
    ComparisonView,
    BatchMatrixView,
    BatchRunCreate,
    MatrixCaseView,
    OpenApiImport,
    OperationResourceMappingCreate,
    OperationResourceMappingUpdate,
    OperationResourceMappingView,
    OperationUpdate,
    OperationView,
    PolicyCreate,
    PolicyUpdate,
    PolicyView,
    ResourceCreate,
    ResourceTypeCreate,
    ResourceTypeUpdate,
    ResourceTypeView,
    ResourceUpdate,
    ResourceView,
    ResourceInspection,
    ResultEvidenceView,
    ResultEvidenceV2View,
    ResultMetadataView,
    RunResultView,
    RunCreate,
    RunView,
)
from backend.app.core.auth import require_admin, require_csrf
from backend.app.domain.contracts import PolicyDecision, RunStatus
from backend.app.persistence.models import Finding, FindingReproduction, Identity, IdentitySecret, OpenApiOperation, OperationResourceMapping, Policy, Project, Resource, ResourceType, Run, RunExecutionStats, RunIdentitySecret, RunResult, Target
from backend.app.workers.queue import request_cancellation
from backend.app.scanner.classification.json_pointer import JsonPointerError, validate_pointer
from backend.app.scanner.classification.policy import PolicyRule, resolve_policy
from backend.app.scanner.matrix.generator import generate_cases
from backend.app.scanner.openapi.parser import OpenApiError, parse_openapi_json
from backend.app.services.batch_plan import BatchPlan, BatchPlanError, build_batch_plan
from backend.app.services.demo_presentation import matrix_rows, public_snapshot
from backend.app.services.run_snapshot import snapshot_batch_run, snapshot_run

router = APIRouter(prefix="/api", tags=["workflow"])


def require_project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    return project


def policy_view(policy: Policy) -> dict[str, object]:
    return {
        "id": policy.id,
        "version": policy.version,
        "operation_id": policy.operation_id,
        "resource_type_id": policy.resource_type_id,
        "decision": policy.decision,
        "identity_id": policy.identity_id,
        "role": policy.role,
        "resource_id": policy.resource_id,
    }


@router.post("/projects/{project_id}/openapi", response_model=list[OperationView])
def import_openapi(project_id: int, payload: OpenApiImport, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> list[OpenApiOperation]:
    require_project(session, project_id)
    try:
        inventory = parse_openapi_json(payload.document)
    except OpenApiError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    for item in inventory:
        existing = session.scalar(select(OpenApiOperation).where(OpenApiOperation.project_id == project_id, OpenApiOperation.operation_key == item.operation_id))
        if existing is None:
            session.add(OpenApiOperation(project_id=project_id, operation_key=item.operation_id, method=item.method, path=item.path, selected=True))
    session.commit()
    return list(session.scalars(select(OpenApiOperation).where(OpenApiOperation.project_id == project_id).order_by(OpenApiOperation.id)))


@router.get("/projects/{project_id}/operations", response_model=list[OperationView])
def list_operations(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[OpenApiOperation]:
    require_project(session, project_id)
    return list(session.scalars(select(OpenApiOperation).where(OpenApiOperation.project_id == project_id).order_by(OpenApiOperation.id)))


@router.patch("/operations/{operation_id}", response_model=OperationView)
def update_operation(operation_id: int, payload: OperationUpdate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> OpenApiOperation:
    operation = session.get(OpenApiOperation, operation_id)
    if operation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy operation.")
    operation.selected = payload.selected
    session.commit()
    session.refresh(operation)
    return operation


@router.post("/projects/{project_id}/resource-types", response_model=ResourceTypeView, status_code=status.HTTP_201_CREATED)
def create_resource_type(project_id: int, payload: ResourceTypeCreate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> ResourceType:
    require_project(session, project_id)
    try:
        validate_pointer(payload.resource_id_pointer)
        for pointer in payload.restricted_pointers:
            validate_pointer(pointer)
    except JsonPointerError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    resource_type = ResourceType(project_id=project_id, **payload.model_dump())
    session.add(resource_type)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Tên loại tài nguyên đã tồn tại.") from error
    session.refresh(resource_type)
    return resource_type


@router.get("/projects/{project_id}/resource-types", response_model=list[ResourceTypeView])
def list_resource_types(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[ResourceType]:
    require_project(session, project_id)
    return list(session.scalars(select(ResourceType).where(ResourceType.project_id == project_id).order_by(ResourceType.id)))


@router.patch("/resource-types/{resource_type_id}", response_model=ResourceTypeView)
def update_resource_type(resource_type_id: int, payload: ResourceTypeUpdate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> ResourceType:
    resource_type = session.get(ResourceType, resource_type_id)
    if resource_type is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy loại tài nguyên.")
    try:
        validate_pointer(payload.resource_id_pointer)
        for pointer in payload.restricted_pointers:
            validate_pointer(pointer)
    except JsonPointerError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    resource_type.name = payload.name
    resource_type.resource_id_pointer = payload.resource_id_pointer
    resource_type.restricted_pointers = payload.restricted_pointers
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Tên loại tài nguyên đã tồn tại.") from error
    session.refresh(resource_type)
    return resource_type


def _resource_view(resource):
    return {"id": resource.id, "resource_type_id": resource.resource_type_id,
            "owner_identity_id": resource.owner_identity_id, "path_parameter": resource.path_parameter,
            "external_id": "[REDACTED]", "resource_alias": f"resource-{resource.id}"}


@router.post("/projects/{project_id}/resources/{resource_id}/inspect", response_model=ResourceInspection)
def inspect_resource(project_id: int, resource_id: int, response: Response,
                     _: None = Depends(require_csrf), session: Session = Depends(get_session)):
    """Explicit admin reveal, never a list/export DTO or an outbound request."""
    import re
    from backend.app.workers.runner import _concrete_path
    resource = session.scalar(select(Resource).join(ResourceType).where(
        Resource.id == resource_id, ResourceType.project_id == project_id))
    if resource is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy resource trong dự án.")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    previews = []
    for operation in session.scalars(select(OpenApiOperation).where(
        OpenApiOperation.project_id == project_id, OpenApiOperation.selected.is_(True),
        OpenApiOperation.method == "GET").order_by(OpenApiOperation.id)):
        if set(re.findall(r"\{([^{}]+)\}", operation.path)) == {resource.path_parameter}:
            previews.append(dict(operation_id=operation.id, method="GET",
                path=_concrete_path(operation.path, resource.path_parameter, resource.external_id)))
    return {**_resource_view(resource), "external_id": resource.external_id, "request_previews": previews}


@router.get("/projects/{project_id}/resources", response_model=list[ResourceView])
def list_resources(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[Resource]:
    require_project(session, project_id)
    return [_resource_view(resource) for resource in session.scalars(
        select(Resource).join(ResourceType).where(ResourceType.project_id == project_id).order_by(Resource.id)
    )]


@router.post("/resource-types/{resource_type_id}/resources", response_model=ResourceView, status_code=status.HTTP_201_CREATED)
def create_resource(resource_type_id: int, payload: ResourceCreate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Resource:
    resource_type = session.get(ResourceType, resource_type_id)
    if resource_type is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy loại tài nguyên.")
    owner = session.get(Identity, payload.owner_identity_id)
    if owner is None or owner.project_id != resource_type.project_id:
        raise HTTPException(status_code=422, detail="Owner phải là danh tính của cùng dự án.")
    resource = Resource(resource_type_id=resource_type_id, **payload.model_dump())
    session.add(resource)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Resource ID đã tồn tại trong loại tài nguyên.") from error
    session.refresh(resource)
    return _resource_view(resource)


@router.patch("/resources/{resource_id}", response_model=ResourceView)
def update_resource(resource_id: int, payload: ResourceUpdate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Resource:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy resource.")
    resource_type = session.get(ResourceType, resource.resource_type_id)
    owner = session.get(Identity, payload.owner_identity_id)
    if resource_type is None or owner is None or owner.project_id != resource_type.project_id:
        raise HTTPException(status_code=422, detail="Owner phải là danh tính của cùng dự án.")
    if payload.external_id == "[REDACTED]":
        raise HTTPException(status_code=422, detail="Bỏ external_id để giữ định danh hiện tại; nhập giá trị mới để thay thế.")
    if payload.external_id is not None:
        resource.external_id = payload.external_id
    resource.owner_identity_id = payload.owner_identity_id
    resource.path_parameter = payload.path_parameter
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Resource ID đã tồn tại trong loại tài nguyên.") from error
    session.refresh(resource)
    return _resource_view(resource)


def mapping_view(mapping: OperationResourceMapping) -> dict[str, object]:
    return {
        "id": mapping.id,
        "project_id": mapping.project_id,
        "operation_id": mapping.operation_id,
        "resource_type_id": mapping.resource_type_id,
        "selected": mapping.selected,
    }


def _mapping_entities(session: Session, project_id: int, operation_id: int, resource_type_id: int) -> tuple[OpenApiOperation, ResourceType]:
    operation = session.get(OpenApiOperation, operation_id)
    resource_type = session.get(ResourceType, resource_type_id)
    if operation is None or resource_type is None or operation.project_id != project_id or resource_type.project_id != project_id:
        raise HTTPException(status_code=422, detail="Operation và resource type phải thuộc cùng dự án.")
    if operation.method != "GET":
        raise HTTPException(status_code=422, detail="Mapping batch chỉ cho phép operation GET.")
    return operation, resource_type


def _validate_mapping_resources(session: Session, operation: OpenApiOperation, resource_type: ResourceType) -> None:
    resources = list(session.scalars(select(Resource).where(Resource.resource_type_id == resource_type.id)))
    if not resources or any("{" + resource.path_parameter + "}" not in operation.path for resource in resources):
        raise HTTPException(status_code=422, detail="Mapping cần ít nhất một resource có path parameter tương thích với operation.")


@router.get("/projects/{project_id}/operation-resource-mappings", response_model=list[OperationResourceMappingView])
def list_operation_resource_mappings(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    require_project(session, project_id)
    return [mapping_view(mapping) for mapping in session.scalars(select(OperationResourceMapping).where(OperationResourceMapping.project_id == project_id).order_by(OperationResourceMapping.id))]


@router.post("/projects/{project_id}/operation-resource-mappings", response_model=OperationResourceMappingView, status_code=status.HTTP_201_CREATED)
def create_operation_resource_mapping(project_id: int, payload: OperationResourceMappingCreate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    require_project(session, project_id)
    operation, resource_type = _mapping_entities(session, project_id, payload.operation_id, payload.resource_type_id)
    if payload.selected:
        _validate_mapping_resources(session, operation, resource_type)
    mapping = OperationResourceMapping(project_id=project_id, **payload.model_dump())
    session.add(mapping)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Mapping operation và resource type đã tồn tại.") from error
    session.refresh(mapping)
    return mapping_view(mapping)


@router.patch("/operation-resource-mappings/{mapping_id}", response_model=OperationResourceMappingView)
def update_operation_resource_mapping(mapping_id: int, payload: OperationResourceMappingUpdate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    mapping = session.get(OperationResourceMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy mapping operation và resource type.")
    operation, resource_type = _mapping_entities(session, mapping.project_id, mapping.operation_id, mapping.resource_type_id)
    if payload.selected:
        _validate_mapping_resources(session, operation, resource_type)
    mapping.selected = payload.selected
    session.commit()
    session.refresh(mapping)
    return mapping_view(mapping)


def _build_project_batch_plan(session: Session, project_id: int, target_id: int) -> BatchPlan:
    target = session.get(Target, target_id)
    if target is None or target.project_id != project_id:
        raise HTTPException(status_code=422, detail="Target phải thuộc dự án.")
    identities = list(session.scalars(select(Identity).where(Identity.project_id == project_id)))
    identity_secrets = list(session.scalars(select(IdentitySecret).join(Identity).where(Identity.project_id == project_id)))
    mappings = list(session.scalars(select(OperationResourceMapping).where(OperationResourceMapping.project_id == project_id, OperationResourceMapping.selected.is_(True))))
    operations = list(session.scalars(select(OpenApiOperation).where(OpenApiOperation.project_id == project_id)))
    resource_types = list(session.scalars(select(ResourceType).where(ResourceType.project_id == project_id)))
    resources = list(session.scalars(select(Resource).join(ResourceType).where(ResourceType.project_id == project_id)))
    policies = list(session.scalars(select(Policy).join(OpenApiOperation).where(OpenApiOperation.project_id == project_id)))
    try:
        return build_batch_plan(
            target=target,
            identities=identities,
            identity_secrets=identity_secrets,
            mappings=mappings,
            operations=operations,
            resource_types=resource_types,
            resources=resources,
            policies=policies,
        )
    except BatchPlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/projects/{project_id}/batch-matrix", response_model=BatchMatrixView)
def get_batch_matrix(project_id: int, target_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> dict[str, object]:
    require_project(session, project_id)
    plan = _build_project_batch_plan(session, project_id, target_id)
    grouped: dict[tuple[int, int], dict[str, object]] = {}
    for item in plan.targets:
        key = (item.operation.id, item.resource_type.id)
        row = grouped.setdefault(key, {
            "operation_id": item.operation.id,
            "operation_path": item.operation.path,
            "resource_type_id": item.resource_type.id,
            "resource_type_name": item.resource_type.name,
            "resource_count": 0,
            "actor_case_count": 0,
        })
        row["resource_count"] = int(row["resource_count"]) + 1
        row["actor_case_count"] = int(row["actor_case_count"]) + len(plan.identities)
    return {
        "identity_count": len(plan.identities),
        "concrete_target_count": len(plan.targets),
        "actor_case_count": plan.actor_case_count,
        "identity_verifications": plan.identity_verifications,
        "owner_baselines": plan.owner_baselines,
        "planned_attempts": plan.planned_attempts,
        "maximum_http_requests": plan.maximum_http_requests,
        "request_limit": plan.target.request_limit,
        "within_request_limit": plan.within_request_limit,
        "targets": list(grouped.values()),
        "cases": [row for item in plan.targets for row in matrix_rows(item.operation, item.resource, plan.identities, item.policies)],
    }


@router.post("/projects/{project_id}/batch-runs", response_model=RunView, status_code=status.HTTP_201_CREATED)
def create_batch_run(project_id: int, payload: BatchRunCreate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    require_project(session, project_id)
    plan = _build_project_batch_plan(session, project_id, payload.target_id)
    if not plan.within_request_limit:
        raise HTTPException(status_code=422, detail="Batch vượt quá giới hạn request của target; hãy tăng giới hạn hoặc thu hẹp mapping đã bật.")
    secrets_by_identity = {secret.identity_id: secret for secret in session.scalars(select(IdentitySecret).join(Identity).where(Identity.project_id == project_id))}
    run = Run(project_id=project_id, status=RunStatus.QUEUED, snapshot=snapshot_batch_run(plan))
    session.add(run)
    session.flush()
    for identity in plan.identities:
        secret = secrets_by_identity[identity.id]
        session.add(RunIdentitySecret(run_id=run.id, identity_id=identity.id, ciphertext=secret.ciphertext, key_version=secret.key_version))
    session.add(RunExecutionStats(run_id=run.id, planned_attempts=plan.planned_attempts))
    session.commit()
    session.refresh(run)
    return _run_view(session, run)


@router.post("/projects/{project_id}/policies", response_model=PolicyView, status_code=status.HTTP_201_CREATED)
def create_policy(project_id: int, payload: PolicyCreate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    require_project(session, project_id)
    operation = session.get(OpenApiOperation, payload.operation_id)
    resource_type = session.get(ResourceType, payload.resource_type_id)
    if operation is None or operation.project_id != project_id or resource_type is None or resource_type.project_id != project_id:
        raise HTTPException(status_code=422, detail="Operation và resource type phải thuộc cùng dự án.")
    if (payload.identity_id is None) == (payload.role is None):
        raise HTTPException(status_code=422, detail="Policy cần đúng một subject: identity hoặc role.")
    if payload.identity_id is not None:
        identity = session.get(Identity, payload.identity_id)
        if identity is None or identity.project_id != project_id:
            raise HTTPException(status_code=422, detail="Identity policy không thuộc dự án.")
    if payload.resource_id is not None:
        resource = session.get(Resource, payload.resource_id)
        if resource is None or resource.resource_type_id != resource_type.id:
            raise HTTPException(status_code=422, detail="Resource policy không thuộc resource type.")
    policy = Policy(**payload.model_dump())
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy_view(policy)


@router.get("/projects/{project_id}/policies", response_model=list[PolicyView])
def list_policies(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    require_project(session, project_id)
    return [policy_view(policy) for policy in session.scalars(select(Policy).where(Policy.operation_id.in_(select(OpenApiOperation.id).where(OpenApiOperation.project_id == project_id))).order_by(Policy.id))]


@router.patch("/policies/{policy_id}", response_model=PolicyView)
def update_policy(policy_id: int, payload: PolicyUpdate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    policy = session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy policy.")
    existing_operation = session.get(OpenApiOperation, policy.operation_id)
    operation = session.get(OpenApiOperation, payload.operation_id)
    resource_type = session.get(ResourceType, payload.resource_type_id)
    if existing_operation is None or operation is None or resource_type is None or operation.project_id != resource_type.project_id or operation.project_id != existing_operation.project_id:
        raise HTTPException(status_code=422, detail="Policy phải giữ operation và resource type trong cùng dự án.")
    if (payload.identity_id is None) == (payload.role is None):
        raise HTTPException(status_code=422, detail="Policy cần đúng một subject: identity hoặc role.")
    if payload.identity_id is not None:
        identity = session.get(Identity, payload.identity_id)
        if identity is None or identity.project_id != operation.project_id:
            raise HTTPException(status_code=422, detail="Identity policy không thuộc dự án.")
    if payload.resource_id is not None:
        resource = session.get(Resource, payload.resource_id)
        if resource is None or resource.resource_type_id != resource_type.id:
            raise HTTPException(status_code=422, detail="Resource policy không thuộc resource type.")
    semantic_fields = ("operation_id", "resource_type_id", "decision", "identity_id", "role", "resource_id")
    if any(getattr(policy, field) != getattr(payload, field) for field in semantic_fields):
        policy.version += 1
    for field in semantic_fields:
        setattr(policy, field, getattr(payload, field))
    session.commit()
    session.refresh(policy)
    return policy_view(policy)


@router.get("/projects/{project_id}/matrix", response_model=list[MatrixCaseView])
def get_matrix(project_id: int, operation_id: int, resource_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    require_project(session, project_id)
    operation = session.get(OpenApiOperation, operation_id)
    resource = session.get(Resource, resource_id)
    if operation is None or operation.project_id != project_id or resource is None:
        raise HTTPException(status_code=422, detail="Operation hoặc resource không hợp lệ.")
    resource_type = session.get(ResourceType, resource.resource_type_id)
    if resource_type is None or resource_type.project_id != project_id:
        raise HTTPException(status_code=422, detail="Resource phải thuộc dự án.")
    identities = list(session.scalars(select(Identity).where(Identity.project_id == project_id)))
    policies = list(session.scalars(select(Policy).where(Policy.operation_id == operation_id, Policy.resource_type_id == resource.resource_type_id)))
    if not operation.selected or operation.method != "GET":
        raise HTTPException(status_code=422, detail="Matrix chỉ cho phép GET đã chọn.")
    mapping = session.scalar(select(OperationResourceMapping).where(
        OperationResourceMapping.project_id == project_id,
        OperationResourceMapping.operation_id == operation.id,
        OperationResourceMapping.resource_type_id == resource.resource_type_id,
        OperationResourceMapping.selected.is_(True)))
    if mapping is None or "{" + resource.path_parameter + "}" not in operation.path or resource.owner_identity_id not in {i.id for i in identities}:
        raise HTTPException(status_code=422, detail="Resource cần mapping GET đã chọn và owner trong dự án.")
    return matrix_rows(operation, resource, identities, policies)


@router.post("/projects/{project_id}/runs", response_model=RunView, status_code=status.HTTP_201_CREATED)
def create_run(project_id: int, payload: RunCreate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Run:
    require_project(session, project_id)
    target = session.get(Target, payload.target_id)
    resource = session.get(Resource, payload.resource_id)
    operation = session.get(OpenApiOperation, payload.operation_id)
    if target is None or target.project_id != project_id or resource is None or operation is None or operation.project_id != project_id:
        raise HTTPException(status_code=422, detail="Target, resource và operation phải thuộc dự án.")
    if not operation.selected or operation.method != "GET":
        raise HTTPException(status_code=422, detail="MVP chỉ cho phép operation GET đã được chọn.")
    resource_type_for_run = session.get(ResourceType, resource.resource_type_id)
    if resource_type_for_run is None or resource_type_for_run.project_id != project_id:
        raise HTTPException(status_code=422, detail="Resource phải thuộc dự án.")
    policies = list(session.scalars(select(Policy).where(Policy.operation_id == operation.id, Policy.resource_type_id == resource.resource_type_id)))
    identities = list(session.scalars(select(Identity).where(Identity.project_id == project_id)))
    secrets_by_identity = {secret.identity_id: secret for secret in session.scalars(select(IdentitySecret).join(Identity).where(Identity.project_id == project_id))}
    if any(identity.id not in secrets_by_identity for identity in identities):
        raise HTTPException(status_code=422, detail="Mọi danh tính trong run phải có bearer token write-only.")
    resource_type = session.get(ResourceType, resource.resource_type_id)
    run = Run(
        project_id=project_id,
        status=RunStatus.QUEUED,
        snapshot=snapshot_run(
            target=target,
            resource=resource,
            resource_type=resource_type,
            policies=policies,
            operation_path=operation.path,
            identities=identities,
        ),
    )
    session.add(run)
    session.flush()
    for identity in identities:
        secret = secrets_by_identity[identity.id]
        session.add(RunIdentitySecret(run_id=run.id, identity_id=identity.id, ciphertext=secret.ciphertext, key_version=secret.key_version))
    session.commit()
    session.refresh(run)
    return _run_view(session, run)


def _run_view(session: Session, run: Run) -> dict[str, object]:
    stats = session.scalar(select(RunExecutionStats).where(RunExecutionStats.run_id == run.id))
    return {
        "id": run.id,
        "project_id": run.project_id,
        "status": run.status,
        "snapshot": public_snapshot(run.snapshot),
        "execution_summary": None if stats is None else {
            "planned_attempts": stats.planned_attempts,
            "transport_attempts": stats.transport_attempts,
            "completed_responses": stats.completed_responses,
            "scope_blocked": stats.scope_blocked,
            "transport_errors": stats.transport_errors,
            "cancelled_cases": stats.cancelled_cases,
        },
    }


@router.get("/projects/{project_id}/runs", response_model=list[RunView])
def list_runs(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    require_project(session, project_id)
    return [_run_view(session, run) for run in session.scalars(select(Run).where(Run.project_id == project_id).order_by(Run.id.desc()))]


def _result_metadata(result: RunResult) -> ResultMetadataView:
    raw = result.response_metadata
    if not isinstance(raw, dict):
        return ResultMetadataView()
    safe = {}
    # Validate each observation separately; malformed historical fields are unavailable.
    for key in ("body_length", "body_truncated", "json_parse_error"):
        if key in raw:
            try:
                safe[key] = getattr(ResultMetadataView.model_validate({key: raw[key]}), key)
            except ValidationError:
                pass
    try:
        candidate = raw.get("evidence")
        if not isinstance(candidate, dict) or type(candidate.get("schema_version")) is not int:
            return ResultMetadataView(**safe)
        evidence = (ResultEvidenceV2View if candidate["schema_version"] == 2 else ResultEvidenceView).model_validate(candidate)
        if evidence.run_id == result.run_id and evidence.case_key == result.case_key:
            safe["evidence"] = evidence
    except ValidationError:
        pass
    return ResultMetadataView(**safe)


@router.get("/runs/{run_id}/results", response_model=list[RunResultView])
def list_results(run_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    if session.get(Run, run_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy.")
    return [
        {
            "case_key": result.case_key,
            "execution_status": result.execution_status,
            "authorization_conclusion": result.authorization_conclusion,
            "reason_codes": result.reason_codes,
            "http_status": result.http_status,
            "response_metadata": _result_metadata(result),
        }
        for result in session.scalars(select(RunResult).where(RunResult.run_id == run_id).order_by(RunResult.id))
    ]


@router.get("/projects/{project_id}/findings")
def list_findings(project_id: int, run_id: int | None = None, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    require_project(session, project_id)
    if run_id is not None:
        run = session.get(Run, run_id)
        if run is None or run.project_id != project_id:
            raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy trong dự án.")
    # Link only persisted reproductions; never reconstruct case provenance from fingerprints.
    links_query = (
        select(FindingReproduction, RunResult)
        .join(RunResult, FindingReproduction.run_result_id == RunResult.id)
        .join(Run, RunResult.run_id == Run.id)
        .join(Finding, FindingReproduction.finding_id == Finding.id)
        .where(Finding.project_id == project_id, Run.project_id == project_id)
        .order_by(FindingReproduction.id)
    )
    if run_id is not None:
        links_query = links_query.where(RunResult.run_id == run_id)
    links: dict[int, list[dict[str, object]]] = {}
    for reproduction, result in session.execute(links_query):
        links.setdefault(reproduction.finding_id, []).append({
            "run_id": result.run_id,
            "run_result_id": result.id,
            "case_key": result.case_key,
            "actor_identity_id": reproduction.actor_identity_id,
            "resource_id": reproduction.resource_id,
        })
    findings = session.scalars(select(Finding).where(Finding.project_id == project_id).order_by(Finding.id.desc()))
    return [
        {
            "id": finding.id,
            "fingerprint": finding.fingerprint,
            "conclusion": finding.conclusion,
            "operation": {"method": finding.operation_method, "path": finding.operation_path},
            "policy": {"id": finding.policy_id, "version": finding.policy_version},
            "reproduction_count": len(links.get(finding.id, [])),
            "reproductions": links.get(finding.id, []),
        }
        for finding in findings
        if run_id is None or finding.id in links
    ]


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_run(run_id: int, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> None:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy.")
    request_cancellation(session, run_id)
    session.commit()


@router.get("/projects/{project_id}/runs/{run_id}/comparison", response_model=ComparisonView)
def get_comparison(project_id: int, run_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> dict:
    """Read persisted observations only. External methods have no verified importer.

    Never join preview/current configuration, CLI files, or legacy keys by similarity.
    A row without a case key remains visible but cannot be matched to another method.
    """
    require_project(session, project_id)
    run = session.get(Run, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy trong dự án.")
    cases = []
    for result in session.scalars(select(RunResult).where(RunResult.run_id == run_id).order_by(RunResult.id)):
        observation = RunResultView(
            case_key=result.case_key, execution_status=result.execution_status,
            authorization_conclusion=result.authorization_conclusion,
            reason_codes=result.reason_codes, http_status=result.http_status,
            response_metadata=_result_metadata(result),
        )
        cases.append(dict(run_id=run_id, case_key=result.case_key, methods=[
            dict(method="MANUAL", execution_status="NOT_RUN"),
            dict(method="T18", execution_status=result.execution_status,
                 observation=observation, provenance=f"run:{run_id}:result:{result.id}"),
            dict(method="ZAP", execution_status="NOT_RUN"),
        ]))
    return dict(run_id=run_id, cases=cases)
