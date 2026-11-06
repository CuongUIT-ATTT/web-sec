"""SQLite-backed FIFO queue with conditional, non-replaying lifecycle transitions."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.domain.contracts import RunStatus
from backend.app.persistence.models import Run


def _transition(session: Session, run_id: int, source: str, destination: str) -> bool:
    result = session.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == source)
        .values(status=destination)
    )
    return bool(result.rowcount)


def interrupt_orphaned_runs(session: Session) -> int:
    """Mark work interrupted by a prior process; never replay uncertain requests."""
    result = session.execute(
        update(Run)
        .where(Run.status.in_([RunStatus.RUNNING, RunStatus.CANCEL_REQUESTED]))
        .values(status=RunStatus.INTERRUPTED)
    )
    return int(result.rowcount or 0)


def claim_next_run(session: Session) -> Run | None:
    """Claim the oldest queued run exactly once with a conditional update."""
    candidate_id = session.scalar(
        select(Run.id).where(Run.status == RunStatus.QUEUED).order_by(Run.id).limit(1)
    )
    if candidate_id is None or not _transition(session, candidate_id, RunStatus.QUEUED, RunStatus.RUNNING):
        return None
    return session.get(Run, candidate_id)


def request_cancellation(session: Session, run_id: int) -> bool:
    """Request cancellation without overwriting a state changed by another actor."""
    return (
        _transition(session, run_id, RunStatus.QUEUED, RunStatus.CANCELLED)
        or _transition(session, run_id, RunStatus.RUNNING, RunStatus.CANCEL_REQUESTED)
    )


def complete_run(session: Session, run_id: int) -> bool:
    return _transition(session, run_id, RunStatus.RUNNING, RunStatus.COMPLETED)


def fail_run(session: Session, run_id: int) -> bool:
    return _transition(session, run_id, RunStatus.RUNNING, RunStatus.FAILED)


def finish_cancellation(session: Session, run_id: int) -> bool:
    return _transition(session, run_id, RunStatus.CANCEL_REQUESTED, RunStatus.CANCELLED)
