"""Uses temporary SQLite only; never contacts lab endpoints."""
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.persistence import models as m


def test_project_deletion_graph_and_guards(tmp_path):
    app = create_app(Settings(database_path=tmp_path / "test.sqlite3", admin_password="password", session_secret="s" * 32, secret_encryption_key=Fernet.generate_key().decode(), target_networks=(), allowed_ports=frozenset(), max_response_bytes=32768, default_timeout_seconds=5))
    with TestClient(app) as client:
        url = "/api/projects/1"
        assert client.request("DELETE", url, json={"confirmation_name": "Delete"}).status_code == 401
        csrf = {"X-CSRF-Token": client.post("/api/auth/login", json={"password": "password"}).json()["csrf_token"]}
        for name in ("Delete", "Keep"):
            assert client.post("/api/projects", json={"name": name}, headers=csrf).status_code == 201
        assert client.request("DELETE", url, json={"confirmation_name": "Delete"}).status_code == 403
        assert client.request("DELETE", url, json={"confirmation_name": "wrong"}, headers=csrf).status_code == 422
        identity = {"display_name": "Alice", "bearer_token": "test-token"}
        assert client.post("/api/projects/1/identities", json=identity, headers=csrf).status_code == 201
        # Name is project scoped, token remains globally unique.
        assert client.post("/api/projects/2/identities", json=identity, headers=csrf).status_code == 409
        assert client.post("/api/projects/2/identities", json={**identity, "bearer_token": "different-token"}, headers=csrf).status_code == 201
        with app.state.session_factory() as s:
            # Seed a connected graph containing every project-owned table.
            target = m.Target(project_id=1, base_url="http://127.0.0.1:5000")
            op = m.OpenApiOperation(project_id=1, operation_key="read", path="/books/{id}")
            rt = m.ResourceType(project_id=1, name="book", resource_id_pointer="/id")
            run = m.Run(project_id=1, status="QUEUED")
            s.add_all([target, op, rt, run]); s.flush()
            resource = m.Resource(resource_type_id=rt.id, external_id="book", owner_identity_id=1, path_parameter="id")
            result = m.RunResult(run_id=run.id, execution_status="COMPLETED_RESPONSE", authorization_conclusion="INCONCLUSIVE")
            finding = m.Finding(project_id=1, fingerprint="f", conclusion="INCONCLUSIVE", operation_method="GET", operation_path="/books/{id}", policy_id=1, policy_version=1, resource_type_id=rt.id, resource_pointer="/id")
            s.add_all([resource, result, finding]); s.flush()
            s.add_all([
                m.IdentityVerification(identity_id=1, target_id=target.id, authentication_passed=True, principal_matched=True, execution_status="COMPLETED_RESPONSE"),
                m.OperationResourceMapping(project_id=1, operation_id=op.id, resource_type_id=rt.id),
                m.Policy(operation_id=op.id, resource_type_id=rt.id, identity_id=1, resource_id=resource.id, decision="ALLOW"),
                m.RunIdentitySecret(run_id=run.id, identity_id=1, ciphertext="fake", key_version=1),
                m.RunExecutionStats(run_id=run.id),
                m.BatchCaseClaim(run_id=run.id, case_key="case", payload_fingerprint="f", run_result_id=result.id),
                m.FindingReproduction(finding_id=finding.id, run_result_id=result.id, actor_identity_id=1, resource_id=resource.id),
                m.ComparisonBundle(project_id=1, content_digest="digest", canonical_json="{}"),
                m.ProjectAuthorizationRevision(project_id=1, revision="revision", configuration={}),
                m.ExternalLabJob(project_id=1, public_id="job", job_kind="test", status="SUCCEEDED"),
            ]); s.commit()
        assert client.request("DELETE", url, json={"confirmation_name": "Delete"}, headers=csrf).status_code == 409
        with app.state.session_factory() as s:
            s.get(m.Run, 1).status = "COMPLETED"
            s.get(m.ExternalLabJob, 1).status = "RUNNING"
            s.commit()
        assert client.request("DELETE", url, json={"confirmation_name": "Delete"}, headers=csrf).status_code == 409
        with app.state.session_factory() as s:
            s.get(m.ExternalLabJob, 1).status = "SUCCEEDED"; s.commit()
        # FK enforcement on the actual deletion connection proves child-first order.
        from sqlalchemy import event
        engine = app.state.session_factory.kw["bind"]
        @event.listens_for(engine, "checkout")
        def enforce(dbapi, record, proxy):
            dbapi.execute("PRAGMA foreign_keys=ON")
        assert client.request("DELETE", url, json={"confirmation_name": "Delete"}, headers=csrf).status_code == 204
        with app.state.session_factory() as s:
            assert not s.execute(text("PRAGMA foreign_key_check")).all()
            for table in m.Base.metadata.sorted_tables:
                count = len(s.execute(select(table)).all())
                assert count == (1 if table.name in {"projects", "identities", "identity_secrets"} else 0), table.name
        assert client.get("/api/projects").json()[0]["name"] == "Keep"
        assert client.request("DELETE", url, json={"confirmation_name": "Delete"}, headers=csrf).status_code == 404
        # Deleted credentials no longer prevent adding the token to another project.
        assert client.post("/api/projects/2/identities", json={**identity, "display_name": "Bob"}, headers=csrf).status_code == 201
