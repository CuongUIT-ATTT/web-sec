from backend.app.domain.contracts import RunStatus
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import Project, Run
from backend.app.workers.queue import claim_next_run, interrupt_orphaned_runs, request_cancellation


def test_two_sessions_only_one_claims_same_run(tmp_path) -> None:
    session_factory = create_session_factory(tmp_path / "claim-race.sqlite3")
    with session_factory.begin() as session:
        project = Project(name="Lab", description="")
        session.add(project)
        session.flush()
        session.add(Run(project_id=project.id, status=RunStatus.QUEUED, snapshot={}))
    first, second = session_factory(), session_factory()
    try:
        claimed_first = claim_next_run(first)
        first.commit()
        claimed_second = claim_next_run(second)
        second.commit()
    finally:
        first.close(); second.close()
    assert claimed_first is not None
    assert claimed_second is None


def test_terminal_runs_reject_cancellation(tmp_path) -> None:
    session_factory = create_session_factory(tmp_path / "terminal.sqlite3")
    with session_factory.begin() as session:
        project = Project(name="Lab", description="")
        session.add(project); session.flush()
        terminal = Run(project_id=project.id, status=RunStatus.COMPLETED, snapshot={})
        session.add(terminal); session.flush()
        assert request_cancellation(session, terminal.id) is False
        assert claim_next_run(session) is None



def test_queue_claim_cancel_and_restart_interruption_are_persistent(tmp_path) -> None:
    session_factory = create_session_factory(tmp_path / "app.sqlite3")
    with session_factory.begin() as session:
        project = Project(name="Lab", description="")
        session.add(project)
        session.flush()
        first = Run(project_id=project.id, status=RunStatus.QUEUED, snapshot={})
        second = Run(project_id=project.id, status=RunStatus.QUEUED, snapshot={})
        session.add_all([first, second])

    with session_factory.begin() as session:
        claimed = claim_next_run(session)
        assert claimed is not None
        assert claimed.status == RunStatus.RUNNING
        assert request_cancellation(session, claimed.id) is True
        assert claimed.status == RunStatus.CANCEL_REQUESTED

    with session_factory.begin() as session:
        assert interrupt_orphaned_runs(session) == 1
        runs = list(session.query(Run).order_by(Run.id))

    assert runs[0].status == RunStatus.INTERRUPTED
    assert runs[1].status == RunStatus.QUEUED
