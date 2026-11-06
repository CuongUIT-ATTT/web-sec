"""Initial browser API for projects, scoped targets, and write-only identities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.schemas import IdentityCreate, IdentityUpdate, IdentityVerificationView, IdentityView, LoginRequest, LoginResponse, ProjectCreate, ProjectUpdate, ProjectView, TargetConnectionView, TargetCreate, TargetUpdate, TargetView
from backend.app.core.auth import establish_admin_session, require_admin, require_csrf, verify_admin_password
from backend.app.core.secrets import SecretBox, SecretError
from backend.app.scanner.classification.json_pointer import JsonPointerError, validate_pointer
from backend.app.scanner.execution.http_client import get_json
from backend.app.scanner.execution.scope import TargetScopeError, build_request_url, validate_base_url
from backend.app.scanner.classification.json_pointer import resolve_pointer
from backend.app.persistence.models import Identity, IdentitySecret, IdentityVerification, Project, Target
from backend.app.services.serializers import serialize_identity

router = APIRouter(prefix="/api", tags=["configuration"])


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def settings(request: Request):
    return request.app.state.settings


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    if not verify_admin_password(payload.password, settings(request)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thông tin đăng nhập không hợp lệ.")
    return LoginResponse(csrf_token=establish_admin_session(request))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, _: None = Depends(require_csrf)) -> None:
    request.session.clear()


@router.post("/projects", response_model=ProjectView, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Project:
    project = Project(name=payload.name, description=payload.description)
    session.add(project)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Tên dự án đã tồn tại.") from error
    session.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectView])
def list_projects(_: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.id)))


@router.patch("/projects/{project_id}", response_model=ProjectView)
def update_project(project_id: int, payload: ProjectUpdate, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    project.name = payload.name
    project.description = payload.description
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Tên dự án đã tồn tại.") from error
    session.refresh(project)
    return project


@router.post("/projects/{project_id}/targets", response_model=TargetView, status_code=status.HTTP_201_CREATED)
def create_target(project_id: int, payload: TargetCreate, request: Request, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Target:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    try:
        base_url = validate_base_url(payload.base_url, settings(request))
        build_request_url(base_url, payload.verification_path, settings(request))
    except TargetScopeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    target = Target(project_id=project_id, base_url=base_url, timeout_seconds=payload.timeout_seconds, request_limit=payload.request_limit, verification_path=payload.verification_path)
    session.add(target)
    session.commit()
    session.refresh(target)
    return target


@router.get("/projects/{project_id}/targets", response_model=list[TargetView])
def list_targets(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[Target]:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    return list(session.scalars(select(Target).where(Target.project_id == project_id).order_by(Target.id)))


@router.patch("/targets/{target_id}", response_model=TargetView)
def update_target(target_id: int, payload: TargetUpdate, request: Request, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> Target:
    target = session.get(Target, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy API đích.")
    try:
        base_url = validate_base_url(payload.base_url, settings(request))
        build_request_url(base_url, payload.verification_path, settings(request))
    except TargetScopeError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    target.base_url = base_url
    target.timeout_seconds = payload.timeout_seconds
    target.request_limit = payload.request_limit
    target.verification_path = payload.verification_path
    session.commit()
    session.refresh(target)
    return target


@router.post("/targets/{target_id}/connection-test", response_model=TargetConnectionView)
async def test_connection(target_id: int, request: Request, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    target = session.get(Target, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy API đích.")
    observation = await get_json(
        base_url=target.base_url,
        api_path=target.verification_path,
        bearer_token=None,
        settings=settings(request),
        timeout_seconds=target.timeout_seconds,
    )
    return {
        "execution_status": observation.execution_status,
        "http_status": observation.status_code,
        "reason_codes": list(observation.reason_codes),
    }


@router.post("/projects/{project_id}/identities", response_model=IdentityView, status_code=status.HTTP_201_CREATED)
def create_identity(project_id: int, payload: IdentityCreate, request: Request, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    try:
        if payload.principal_pointer:
            validate_pointer(payload.principal_pointer)
        ciphertext, fingerprint = SecretBox.from_key(settings(request).secret_encryption_key).encrypt_bearer(payload.bearer_token)
    except (JsonPointerError, SecretError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    identity = Identity(
        project_id=project_id,
        display_name=payload.display_name,
        role=payload.role,
        principal_pointer=payload.principal_pointer,
        expected_principal=payload.expected_principal,
    )
    session.add(identity)
    try:
        session.flush()
        session.add(IdentitySecret(identity_id=identity.id, ciphertext=ciphertext, fingerprint=fingerprint, key_version=1))
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Danh tính hoặc bearer token đã tồn tại.") from error
    session.refresh(identity)
    return serialize_identity(identity)


@router.patch("/identities/{identity_id}", response_model=IdentityView)
def update_identity(identity_id: int, payload: IdentityUpdate, request: Request, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    identity = session.get(Identity, identity_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy danh tính.")
    try:
        if payload.principal_pointer:
            validate_pointer(payload.principal_pointer)
        ciphertext = fingerprint = None
        if payload.bearer_token is not None:
            ciphertext, fingerprint = SecretBox.from_key(settings(request).secret_encryption_key).encrypt_bearer(payload.bearer_token)
    except (JsonPointerError, SecretError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    identity.display_name = payload.display_name
    identity.role = payload.role
    identity.principal_pointer = payload.principal_pointer
    identity.expected_principal = payload.expected_principal
    if ciphertext is not None and fingerprint is not None:
        if identity.secret is None:
            session.add(IdentitySecret(identity_id=identity.id, ciphertext=ciphertext, fingerprint=fingerprint, key_version=1))
        else:
            identity.secret.ciphertext = ciphertext
            identity.secret.fingerprint = fingerprint
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="Danh tính hoặc bearer token đã tồn tại.") from error
    session.refresh(identity)
    return serialize_identity(identity)


@router.post("/identities/{identity_id}/verify", response_model=IdentityVerificationView)
async def verify_identity(identity_id: int, target_id: int, request: Request, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    identity = session.get(Identity, identity_id)
    target = session.get(Target, target_id)
    if identity is None or target is None or identity.project_id != target.project_id or identity.secret is None:
        raise HTTPException(status_code=422, detail="Danh tính, API đích hoặc bearer token không hợp lệ.")
    try:
        token = SecretBox.from_key(settings(request).secret_encryption_key).decrypt_bearer(identity.secret.ciphertext)
    except SecretError as error:
        raise HTTPException(status_code=422, detail="Không thể dùng bearer token đã lưu.") from error
    observation = await get_json(
        base_url=target.base_url,
        api_path=target.verification_path,
        bearer_token=token,
        settings=settings(request),
        timeout_seconds=target.timeout_seconds,
    )
    authentication_passed = observation.execution_status.value == "COMPLETED_RESPONSE" and observation.status_code is not None and 200 <= observation.status_code < 300
    principal_matched = False
    if authentication_passed and identity.principal_pointer and identity.expected_principal and observation.json_body is not None:
        try:
            principal_matched = str(resolve_pointer(observation.json_body, identity.principal_pointer)) == identity.expected_principal
        except JsonPointerError:
            principal_matched = False
    reason_codes = list(observation.reason_codes)
    if authentication_passed and not principal_matched:
        reason_codes.append("evidence.principal_mismatch")
    session.add(IdentityVerification(
        identity_id=identity.id,
        target_id=target.id,
        authentication_passed=authentication_passed,
        principal_matched=principal_matched,
        execution_status=observation.execution_status,
        reason_codes=reason_codes,
    ))
    session.commit()
    return {
        "authentication_passed": authentication_passed,
        "principal_matched": principal_matched,
        "principal_confirmed": authentication_passed and principal_matched,
        "execution_status": observation.execution_status,
        "reason_codes": reason_codes,
    }


@router.get("/projects/{project_id}/identities", response_model=list[IdentityView])
def list_identities(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.")
    identities = session.scalars(select(Identity).where(Identity.project_id == project_id).order_by(Identity.id))
    return [serialize_identity(identity) for identity in identities]
