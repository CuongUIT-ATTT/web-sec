"""Durable lifecycle transitions for fixed operator-side read-only lab jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.domain.contracts import EXTERNAL_LAB_ACTIVE_STATUSES, EXTERNAL_LAB_TERMINAL_STATUSES, ExternalLabJobKind, ExternalLabJobStatus
from backend.app.persistence.models import ExternalLabJob, Project


def now() -> datetime:
    return datetime.now(UTC)


def job_view(job: ExternalLabJob) -> dict[str, object]:
    return {
        "public_id": job.public_id,
        "project_id": job.project_id,
        "job_kind": job.job_kind,
        "protocol_version": job.protocol_version,
        "status": job.status,
        "requested_at": job.created_at,
        "dispatched_at": job.dispatched_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "cancel_requested_at": job.cancellation_requested_at,
        "result_summary": job.result_summary,
        "artifact_manifest_sha256": job.artifact_manifest_sha256,
        "failure_code": job.failure_code,
    }


def create_read_only_job(session: Session, project_id: int) -> ExternalLabJob:
    if session.get(Project, project_id) is None:
        raise LookupError("project")
    existing = session.scalar(
        select(ExternalLabJob.id).where(ExternalLabJob.status.in_(EXTERNAL_LAB_ACTIVE_STATUSES)).limit(1)
    )
    if existing is not None:
        raise RuntimeError("active_job")
    job = ExternalLabJob(
        public_id=str(uuid4()),
        project_id=project_id,
        job_kind=ExternalLabJobKind.READ_ONLY_VAMPI_VERIFICATION_V1,
        protocol_version=1,
        status=ExternalLabJobStatus.QUEUED,
    )
    session.add(job)
    session.flush()
    return job


def request_cancellation(session: Session, public_id: str) -> bool:
    job = session.scalar(select(ExternalLabJob).where(ExternalLabJob.public_id == public_id))
    if job is None or job.status in EXTERNAL_LAB_TERMINAL_STATUSES:
        return False
    if job.status == ExternalLabJobStatus.QUEUED:
        job.status = ExternalLabJobStatus.CANCELLED
        job.finished_at = now()
        job.failure_code = "CANCELLED"
    elif job.status != ExternalLabJobStatus.CANCEL_REQUESTED:
        job.status = ExternalLabJobStatus.CANCEL_REQUESTED
        job.cancellation_requested_at = now()
    return True


def claim_next_job(session: Session) -> ExternalLabJob | None:
    candidate_id = session.scalar(
        select(ExternalLabJob.id).where(ExternalLabJob.status == ExternalLabJobStatus.QUEUED).order_by(ExternalLabJob.id).limit(1)
    )
    if candidate_id is None:
        return None
    transitioned = session.execute(
        update(ExternalLabJob)
        .where(ExternalLabJob.id == candidate_id, ExternalLabJob.status == ExternalLabJobStatus.QUEUED)
        .values(status=ExternalLabJobStatus.DISPATCHING, dispatched_at=now(), dispatch_attempts=ExternalLabJob.dispatch_attempts + 1)
    )
    return session.get(ExternalLabJob, candidate_id) if transitioned.rowcount else None


def mark_submission_failed(session: Session, public_id: str, failure_code: str) -> None:
    session.execute(
        update(ExternalLabJob)
        .where(ExternalLabJob.public_id == public_id, ExternalLabJob.status == ExternalLabJobStatus.DISPATCHING)
        .values(status=ExternalLabJobStatus.FAILED, failure_code=failure_code, finished_at=now())
    )


def mark_submitted(session: Session, public_id: str) -> None:
    session.execute(
        update(ExternalLabJob)
        .where(ExternalLabJob.public_id == public_id, ExternalLabJob.status == ExternalLabJobStatus.DISPATCHING)
        .values(status=ExternalLabJobStatus.SUBMITTED)
    )


def cancellation_requests(session: Session) -> list[ExternalLabJob]:
    return list(session.scalars(
        select(ExternalLabJob).where(ExternalLabJob.status == ExternalLabJobStatus.CANCEL_REQUESTED).order_by(ExternalLabJob.id)
    ))


def mark_orphaned_jobs(session: Session) -> int:
    """Never replay work that may already have run when the web process restarted."""
    result = session.execute(
        update(ExternalLabJob)
        .where(ExternalLabJob.status.in_({ExternalLabJobStatus.DISPATCHING, ExternalLabJobStatus.SUBMITTED, ExternalLabJobStatus.RUNNING, ExternalLabJobStatus.CANCEL_REQUESTED}))
        .values(status=ExternalLabJobStatus.UNKNOWN, failure_code="UNKNOWN", finished_at=now())
    )
    return int(result.rowcount or 0)


def apply_bridge_event(session: Session, job: ExternalLabJob, *, sequence: int, status: ExternalLabJobStatus, started_at: datetime | None, finished_at: datetime | None, failure_code: str | None, summary: dict[str, object], artifact_manifest_sha256: str | None) -> bool:
    """Apply a monotonic, typed callback without reviving terminal evidence."""
    if sequence <= job.bridge_sequence or job.status in EXTERNAL_LAB_TERMINAL_STATUSES:
        return False
    allowed = {
        ExternalLabJobStatus.DISPATCHING: {ExternalLabJobStatus.SUBMITTED, ExternalLabJobStatus.RUNNING, ExternalLabJobStatus.FAILED, ExternalLabJobStatus.CANCELLED},
        ExternalLabJobStatus.SUBMITTED: {ExternalLabJobStatus.RUNNING, ExternalLabJobStatus.SUCCEEDED, ExternalLabJobStatus.FAILED, ExternalLabJobStatus.CANCELLED, ExternalLabJobStatus.INTERRUPTED},
        ExternalLabJobStatus.RUNNING: {ExternalLabJobStatus.SUCCEEDED, ExternalLabJobStatus.FAILED, ExternalLabJobStatus.CANCELLED, ExternalLabJobStatus.INTERRUPTED},
        ExternalLabJobStatus.CANCEL_REQUESTED: {ExternalLabJobStatus.SUCCEEDED, ExternalLabJobStatus.FAILED, ExternalLabJobStatus.CANCELLED, ExternalLabJobStatus.INTERRUPTED},
    }
    if status not in allowed.get(ExternalLabJobStatus(job.status), set()):
        return False
    job.bridge_sequence = sequence
    job.status = status
    job.started_at = started_at or job.started_at
    job.finished_at = finished_at or (now() if status in EXTERNAL_LAB_TERMINAL_STATUSES else None)
    job.failure_code = failure_code
    job.result_summary = summary
    job.artifact_manifest_sha256 = artifact_manifest_sha256
    return True
