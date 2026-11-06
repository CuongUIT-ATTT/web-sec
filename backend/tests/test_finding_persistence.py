from backend.app.domain.contracts import AuthorizationConclusion, PolicyDecision
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import Project, Run, RunResult
from backend.app.scanner.classification.policy import PolicyRule
from backend.app.services.findings import record_confirmed_reproduction


def test_repeated_reproduction_is_idempotent(tmp_path) -> None:
    factory = create_session_factory(tmp_path / "app.sqlite3")
    with factory.begin() as session:
        project = Project(name="lab", description="")
        session.add(project); session.flush()
        run = Run(project_id=project.id, status="COMPLETED", snapshot={})
        session.add(run); session.flush()
        result = RunResult(run_id=run.id, case_key="case", execution_status="COMPLETED_RESPONSE", authorization_conclusion=AuthorizationConclusion.CONFIRMED_VIOLATION, reason_codes=[], http_status=200, response_metadata={})
        session.add(result); session.flush()
        rule = PolicyRule(1, 1, 2, 3, 4, None, None, PolicyDecision.DENY)
        kwargs = dict(project_id=project.id, run_result=result, actor_identity_id=4, resource_id=5, operation_path="/books/{id}", resource_pointer="/data/id", restricted_pointers=("/data/secret",), policy=rule)
        record_confirmed_reproduction(session, **kwargs)
        record_confirmed_reproduction(session, **kwargs)
    with factory() as session:
        from backend.app.persistence.models import Finding, FindingReproduction
        assert session.query(Finding).count() == 1
        assert session.query(FindingReproduction).count() == 1
