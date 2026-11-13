"""Browser and bridge callback API for a single fixed read-only external lab workflow."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.routes import get_session, settings
from backend.app.core.auth import require_admin, require_csrf
from backend.app.domain.contracts import ExternalLabJobStatus
from backend.app.external_lab.contracts import BRIDGE_EVENT_AUDIENCE, BridgeJobEvent, BridgeProtocolError, verify_signed_request
from backend.app.external_lab.service import apply_bridge_event, create_read_only_job, job_view, request_cancellation
from backend.app.persistence.models import BridgeNonce, ExternalLabJob

router = APIRouter(prefix="/api", tags=["external-lab"])
internal_router = APIRouter(prefix="/api/internal/bridge", tags=["external-lab-internal"])


def _project_jobs(session: Session, project_id: int) -> list[ExternalLabJob]:
    return list(session.scalars(select(ExternalLabJob).where(ExternalLabJob.project_id == project_id).order_by(ExternalLabJob.id.desc())))


@router.get("/projects/{project_id}/external-lab-jobs")
def list_external_lab_jobs(project_id: int, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> list[dict[str, object]]:
    return [job_view(job) for job in _project_jobs(session, project_id)]


@router.post("/projects/{project_id}/external-lab-jobs/read-only-verification", status_code=status.HTTP_201_CREATED)
def create_external_lab_job(project_id: int, request: Request, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> dict[str, object]:
    if not settings(request).external_lab_bridge_enabled:
        raise HTTPException(status_code=409, detail="Operator-side read-only lab bridge is disabled.")
    try:
        job = create_read_only_job(session, project_id)
        session.commit()
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án.") from error
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail="A read-only external lab job is already active.") from error
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="A read-only external lab job is already active.") from error
    session.refresh(job)
    return job_view(job)


@router.get("/external-lab-jobs/{public_id}")
def get_external_lab_job(public_id: str, _: None = Depends(require_admin), session: Session = Depends(get_session)) -> dict[str, object]:
    job = session.scalar(select(ExternalLabJob).where(ExternalLabJob.public_id == public_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy external lab job.")
    return job_view(job)


@router.post("/external-lab-jobs/{public_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_external_lab_job(public_id: str, _: None = Depends(require_csrf), session: Session = Depends(get_session)) -> None:
    if not request_cancellation(session, public_id):
        raise HTTPException(status_code=409, detail="External lab job không thể bị hủy ở trạng thái hiện tại.")
    session.commit()


@internal_router.post("/jobs/{public_id}/events", status_code=status.HTTP_204_NO_CONTENT)
async def receive_bridge_event(public_id: str, request: Request, session: Session = Depends(get_session)) -> None:
    configured = settings(request)
    if not configured.external_lab_bridge_enabled or not configured.external_lab_bridge_shared_secret:
        raise HTTPException(status_code=404, detail="Not found.")
    body = await request.body()
    if len(body) > configured.external_lab_bridge_max_body_bytes:
        raise HTTPException(status_code=413, detail="Bridge event too large.")
    try:
        nonce_hash = verify_signed_request(
            configured.external_lab_bridge_shared_secret,
            method=request.method,
            path=request.url.path,
            body=body,
            timestamp=request.headers.get("X-Bridge-Timestamp"),
            nonce=request.headers.get("X-Bridge-Nonce"),
            audience=request.headers.get("X-Bridge-Audience"),
            signature=request.headers.get("X-Bridge-Signature"),
            expected_audience=BRIDGE_EVENT_AUDIENCE,
            max_skew_seconds=configured.external_lab_bridge_clock_skew_seconds,
        )
        event = BridgeJobEvent.model_validate_json(body)
    except BridgeProtocolError as error:
        raise HTTPException(status_code=401, detail="Bridge authentication failed.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Bridge event rejected.") from error
    now = datetime.now(UTC)
    session.execute(delete(BridgeNonce).where(BridgeNonce.expires_at < now))
    if session.scalar(select(BridgeNonce.id).where(BridgeNonce.nonce_hash == nonce_hash)) is not None:
        raise HTTPException(status_code=409, detail="Bridge event replay rejected.")
    job = session.scalar(select(ExternalLabJob).where(ExternalLabJob.public_id == public_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Not found.")
    applied = apply_bridge_event(
        session,
        job,
        sequence=event.sequence,
        status=event.status,
        started_at=datetime.fromtimestamp(event.started_at, UTC) if event.started_at else None,
        finished_at=datetime.fromtimestamp(event.finished_at, UTC) if event.finished_at else None,
        failure_code=event.failure_code,
        summary=event.summary,
        artifact_manifest_sha256=event.artifact_manifest_sha256,
    )
    if not applied:
        raise HTTPException(status_code=409, detail="Bridge event state transition rejected.")
    session.add(
        BridgeNonce(
            audience=BRIDGE_EVENT_AUDIENCE,
            nonce_hash=nonce_hash,
            expires_at=datetime.fromtimestamp(
                int(request.headers["X-Bridge-Timestamp"])
                + configured.external_lab_bridge_clock_skew_seconds,
                UTC,
            ),
        )
    )
    session.commit()
