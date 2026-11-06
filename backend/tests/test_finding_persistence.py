from backend.app.domain.contracts import AuthorizationConclusion
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import Project, Run, RunResult
from backend.app.scanner.classification.policy import PolicyRule
from backend.app.domain.contracts import PolicyDecision
from backend.app.services.findings import record_confirmed_reproduction


def test_reverse_directions_create_one_group_with_two_reproductions(tmp_path) -> None:
    session_factory = create_session_factory(tmp_path / "app.sqlite3")
    with session_factory.begin() as session:
        project = Project(name="Lab", description="")
        session.add(project)
        session.flush()
        run = Run(project_id=project.id, snapshot={})
        session.add(run)
        session.flush()
        first = RunResult(run_id=run.id, case_key="A-B", execution_status="COMPLETED_RESPONSE", authorization_conclusion=AuthorizationConclusion.CONFIRMED_VIOLATION, reason_codes=[], http_status=200, response_metadata={})
        second = RunResult(run_id=run.id, case_key="B-A", execution_status="COMPLETED_RESPONSE", authorization_conclusion=AuthorizationConclusion.CONFIRMED_VIOLATION, reason_codes=[], http_status=200, response_metadata={})
        session.add_all([first, second])
        session.flush()
        policy = PolicyRule(8, 2, 4, 3, 1, None, None, PolicyDecision.DENY)
        first_group = record_confirmed_reproduction(session, project_id=project.id, run_result=first, actor_identity_id=1, resource_id=11, operation_path="/books/{id}", resource_pointer="/data/id", restricted_pointers=("/data/secret",), policy=policy)
        second_group = record_confirmed_reproduction(session, project_id=project.id, run_result=second, actor_identity_id=2, resource_id=12, operation_path="/books/{id}", resource_pointer="/data/id", restricted_pointers=("/data/secret",), policy=policy)

    with session_factory() as session:
        from backend.app.persistence.models import Finding, FindingReproduction
        assert session.query(Finding).count() == 1
        assert session.query(FindingReproduction).count() == 2

    assert first_group.fingerprint == second_group.fingerprint
    assert "book" not in first_group.fingerprint
