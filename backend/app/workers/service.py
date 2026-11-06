"""Single-process polling worker; one queued run is executed at a time."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import sessionmaker

from backend.app.core.settings import Settings
from backend.app.persistence.models import Run
from backend.app.workers.queue import claim_next_run, interrupt_orphaned_runs
from backend.app.workers.runner import execute_run

LOGGER = logging.getLogger(__name__)


async def worker_loop(session_factory: sessionmaker, settings: Settings, stop_event: asyncio.Event) -> None:
    """Claim FIFO work without replaying anything active when the process stopped."""
    with session_factory.begin() as session:
        interrupt_orphaned_runs(session)
    while not stop_event.is_set():
        with session_factory.begin() as session:
            run = claim_next_run(session)
            run_id = run.id if run is not None else None
        if run_id is None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.25)
            except TimeoutError:
                continue
            continue
        try:
            with session_factory.begin() as session:
                run = session.get(Run, run_id)
                if run is not None:
                    await execute_run(session, run, settings)
        except Exception:  # no request/body information is logged from a failed run
            LOGGER.exception("Authorization run failed internally: run_id=%s", run_id)
            with session_factory.begin() as session:
                run = session.get(Run, run_id)
                if run is not None:
                    run.status = "FAILED"
