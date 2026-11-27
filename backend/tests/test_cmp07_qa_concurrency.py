"""Independent file-backed SQLite race checks; no API/lab traffic."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import Project, Run, RunResult, Finding, FindingReproduction
from backend.app.domain.contracts import RunStatus
from backend.app.workers.queue import (claim_next_run, request_cancellation,
    complete_run, finish_cancellation, interrupt_orphaned_runs)


def seed(tmp_path, state):
    factory = create_session_factory(tmp_path/'race.sqlite3')
    with factory.begin() as session:
        p = Project(name='synthetic')
        session.add(p); session.flush()
        r = Run(project_id=p.id, status=state, snapshot={})
        session.add(r); session.flush()
        run_id = r.id
    return factory, run_id


def test_two_concurrent_sessions_claim_once(tmp_path):
    factory, run_id = seed(tmp_path, RunStatus.QUEUED)
    barrier = Barrier(2)
    def claim():
        with factory.begin() as session:
            barrier.wait(timeout=3)
            row = claim_next_run(session)
            return row.id if row else None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        results = [f.result(timeout=5) for f in futures]
    assert results.count(run_id) == 1 and results.count(None) == 1
    with factory.begin() as session:
        assert interrupt_orphaned_runs(session) == 1
        assert claim_next_run(session) is None
        assert session.get(Run, run_id).status == RunStatus.INTERRUPTED
        for model in (RunResult, Finding, FindingReproduction):
            assert session.query(model).count() == 0


def test_cancel_completion_race_has_one_terminal_outcome(tmp_path):
    factory, run_id = seed(tmp_path, RunStatus.RUNNING)
    barrier = Barrier(2)
    def transition(fn):
        with factory.begin() as session:
            barrier.wait(timeout=3)
            return fn(session, run_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(transition, fn) for fn in (complete_run, request_cancellation)]
        wins = [f.result(timeout=5) for f in futures]
    assert sum(wins) == 1
    with factory.begin() as session:
        state = session.get(Run, run_id).status
        if state == RunStatus.CANCEL_REQUESTED:
            assert finish_cancellation(session, run_id) is True
        else:
            assert state == RunStatus.COMPLETED
        assert request_cancellation(session, run_id) is False
        assert complete_run(session, run_id) is False
