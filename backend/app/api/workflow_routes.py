"""Vertical-slice workflow API: OpenAPI inventory, resources, policies, matrix, and run snapshots."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.routes import get_session
from backend.app.api.workflow_schemas import (
    MatrixCaseView,
    OpenApiImport,
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
    RunCreate,
    RunView,
)
from backend.app.core.auth import require_admin, require_csrf
from backend.app.domain.contracts import PolicyDecision, RunStatus
from backend.app.persistence.models import Finding, FindingReproduction, Identity, IdentitySecret, OpenApiOperation, Policy, Project, Resource, ResourceType, Run, RunIdentitySecret, RunResult, Target
from backend.app.scanner.classification.json_pointer import JsonPointerError, validate_pointer
from backend.app.scanner.classification.policy import PolicyRule, resolve_policy
from backend.app.scanner.matrix.generator import generate_cases
from backend.app.scanner.openapi.parser import OpenApiError, parse_openapi_json
from backend.app.services.run_snapshot import snapshot_run

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


@router.get("/projects/{project_id}/resources", response_model=list[ResourceView])
def list_resources(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[Resource]:
    require_project(session, project_id)
    return list(session.scalars(
        select(Resource).join(ResourceType).where(ResourceType.project_id == project_id).order_by(Resource.id)
    ))


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
    return resource


@router.patch("/resources/{resource_id}", response_model=ResourceView)
def update_resource(resource_id: int, payload: ResourceUpdate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Resource:
    resource = session.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy resource.")
    resource_type = session.get(ResourceType, resource.resource_type_id)
    owner = session.get(Identity, payload.owner_identity_id)
    if resource_type is None or owner is None or owner.project_id != resource_type.project_id:
        raise HTTPException(status_code=422, detail="Owner phải là danh tính của cùng dự án.")
    resource.external_id = payload.external_id
    resource.owner_identity_id = payload.owner_identity_id
    resource.path_parameter = payload.path_parameter
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Resource ID đã tồn tại trong loại tài nguyên.") from error
    session.refresh(resource)
    return resource


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
    resolutions = {
        identity.id: resolve_policy(
            [PolicyRule(policy.id, policy.version, policy.operation_id, policy.resource_type_id, policy.identity_id, policy.role, policy.resource_id, PolicyDecision(policy.decision)) for policy in policies],
            operation_id=operation_id,
            resource_type_id=resource.resource_type_id,
            identity_id=identity.id,
            role=identity.role,
            resource_id=resource.id,
        )
        for identity in identities
    }
    cases = generate_cases(
        resource_id=resource.id,
        owner_identity_id=resource.owner_identity_id,
        actor_identity_ids=[identity.id for identity in identities],
        resolutions=resolutions,
        verified_identity_ids=set(),
    )
    return [
        {
            "case_key": case.case_key,
            "control_type": case.control_type,
            "actor_identity_id": case.actor_identity_id,
            "resource_id": case.resource_id,
            "policy_status": case.policy_status,
            "warnings": list(case.warnings),
        }
        for case in cases
    ]


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
    return run


@router.get("/projects/{project_id}/runs", response_model=list[RunView])
def list_runs(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[Run]:
    require_project(session, project_id)
    return list(session.scalars(select(Run).where(Run.project_id == project_id).order_by(Run.id.desc())))


@router.get("/runs/{run_id}/results")
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
            "response_metadata": result.response_metadata,
        }
        for result in session.scalars(select(RunResult).where(RunResult.run_id == run_id).order_by(RunResult.id))
    ]


@router.get("/projects/{project_id}/findings")
def list_findings(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    require_project(session, project_id)
    findings = list(session.scalars(select(Finding).where(Finding.project_id == project_id).order_by(Finding.id.desc())))
    return [
        {
            "id": finding.id,
            "fingerprint": finding.fingerprint,
            "conclusion": finding.conclusion,
            "operation": {"method": finding.operation_method, "path": finding.operation_path},
            "policy": {"id": finding.policy_id, "version": finding.policy_version},
            "reproduction_count": session.scalar(select(func.count(FindingReproduction.id)).where(FindingReproduction.finding_id == finding.id)) or 0,
        }
        for finding in findings
    ]


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_run(run_id: int, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> None:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lượt chạy.")
    if run.status == RunStatus.QUEUED:
        run.status = RunStatus.CANCELLED
    elif run.status == RunStatus.RUNNING:
        run.status = RunStatus.CANCEL_REQUESTED
    session.commit()
