"""SQLite-backed FIFO run queue with explicit restart interruption semantics."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.domain.contracts import RunStatus
from backend.app.persistence.models import Run


def interrupt_orphaned_runs(session: Session) -> int:
    """Mark work interrupted by a prior process; never replay unobserved requests."""
    result = session.execute(
        update(Run)
        .where(Run.status.in_([RunStatus.RUNNING, RunStatus.CANCEL_REQUESTED]))
        .values(status=RunStatus.INTERRUPTED)
    )
    return int(result.rowcount or 0)


def claim_next_run(session: Session) -> Run | None:
    """Claim the oldest queued job transactionally in the single-process MVP."""
    run = session.scalar(select(Run).where(Run.status == RunStatus.QUEUED).order_by(Run.id).limit(1))
    if run is None:
        return None
    run.status = RunStatus.RUNNING
    session.flush()
    return run


def request_cancellation(session: Session, run_id: int) -> bool:
    run = session.get(Run, run_id)
    if run is None or run.status not in {RunStatus.QUEUED, RunStatus.RUNNING}:
        return False
    run.status = RunStatus.CANCELLED if run.status == RunStatus.QUEUED else RunStatus.CANCEL_REQUESTED
    return True
