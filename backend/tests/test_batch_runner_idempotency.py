import ipaddress
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.app.core.secrets import SecretBox
from backend.app.core.settings import Settings
from backend.app.domain.contracts import RunStatus
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import BatchCaseClaim, Project, Run, RunIdentitySecret, RunResult
from backend.app.scanner.execution.http_client import HttpObservation
from backend.app.domain.contracts import ExecutionStatus
from backend.app.workers import runner


def settings(key: str) -> Settings:
    return Settings(Path("unused.sqlite3"), "password", "s" * 32, key, (ipaddress.ip_network("127.0.0.1/32"),), frozenset({5000}), 32768, 5.0)


def snapshot() -> dict:
    return {
        "schema_version": 2, "run_kind": "BATCH_ALL_SELECTED",
        "target": {"base_url": "http://127.0.0.1:5000", "verification_path": "/me", "timeout_seconds": 5, "request_limit": 5},
        "request_plan": {"identity_verifications": 2, "owner_baselines": 1, "actor_cases": 2, "planned_attempts": 5, "maximum_http_requests": 5},
        "identities": [
            {"id": 1, "role": "reader", "principal_pointer": "/user", "expected_principal": "a"},
            {"id": 2, "role": "reader", "principal_pointer": "/user", "expected_principal": "b"},
        ],
        "targets": [{
            "operation": {"id": 1, "path": "/books/{id}", "method": "GET"},
            "resource": {"id": 1, "external_id": "book", "resource_type_id": 1, "owner_identity_id": 1, "path_parameter": "id", "resource_id_pointer": "/id", "restricted_pointers": ["/secret"]},
            "policies": [],
        }],
    }


@pytest.mark.asyncio
async def test_completed_batch_is_not_replayed(monkeypatch, tmp_path) -> None:
    key = Fernet.generate_key().decode("ascii")
    box = SecretBox.from_key(key)
    encrypted_a, _ = box.encrypt_bearer("a")
    encrypted_b, _ = box.encrypt_bearer("b")
    calls: list[str] = []

    async def fake_get_json(*, api_path: str, bearer_token: str | None, **kwargs) -> HttpObservation:
        calls.append(api_path)
        if api_path == "/me":
            return HttpObservation(ExecutionStatus.COMPLETED_RESPONSE, 200, {"user": bearer_token}, 1, False, False, ())
        return HttpObservation(ExecutionStatus.COMPLETED_RESPONSE, 200, {"id": "book", "secret": "redacted"}, 1, False, False, ())

    monkeypatch.setattr(runner, "get_json", fake_get_json)
    factory = create_session_factory(tmp_path / "app.sqlite3")
    with factory.begin() as session:
        project = Project(name="lab", description="")
        session.add(project); session.flush()
        run = Run(project_id=project.id, status=RunStatus.RUNNING, snapshot=snapshot())
        session.add(run); session.flush()
        session.add_all([
            RunIdentitySecret(run_id=run.id, identity_id=1, ciphertext=encrypted_a, key_version=1),
            RunIdentitySecret(run_id=run.id, identity_id=2, ciphertext=encrypted_b, key_version=1),
        ])
    with factory() as session:
        assert await runner.execute_run(session, session.query(Run).one(), settings(key)) is True
        session.commit()
    first_call_count = len(calls)
    with factory() as session:
        assert await runner.execute_run(session, session.query(Run).one(), settings(key)) is False
        session.commit()
    with factory() as session:
        assert session.query(Run).one().status == RunStatus.COMPLETED
        assert session.query(RunResult).count() == 2
        assert session.query(BatchCaseClaim).count() == 2
    assert len(calls) == first_call_count == 5
