import ipaddress
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.app.core.secrets import SecretBox
from backend.app.core.settings import Settings
from backend.app.domain.contracts import AuthorizationConclusion, ExecutionStatus, RunStatus
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import Finding, FindingReproduction, Project, Run, RunIdentitySecret, RunResult
from backend.app.scanner.execution.http_client import HttpObservation
from backend.app.workers import runner


def observation(status: int, body: dict) -> HttpObservation:
    return HttpObservation(ExecutionStatus.COMPLETED_RESPONSE, status, body, 1, False, False, ("execution.http_response",))


@pytest.mark.asyncio
async def test_run_worker_uses_fresh_principal_and_owner_controls(monkeypatch, tmp_path) -> None:
    key = Fernet.generate_key().decode("ascii")
    settings = Settings(
        database_path=Path("unused.sqlite3"),
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key=key,
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32768,
        default_timeout_seconds=5.0,
    )
    box = SecretBox.from_key(key)
    alice_ciphertext, _ = box.encrypt_bearer("alice-token")
    bob_ciphertext, _ = box.encrypt_bearer("bob-token")
    session_factory = create_session_factory(tmp_path / "app.sqlite3")

    async def fake_get_json(*, api_path: str, bearer_token: str | None, **kwargs) -> HttpObservation:
        if api_path == "/me":
            principal = "alice" if bearer_token == "alice-token" else "bob"
            return observation(200, {"data": {"username": principal}})
        if bearer_token == "alice-token":
            return observation(200, {"data": {"id": "book-1", "secret": "owner-secret"}})
        return observation(403, {"data": {"id": "book-1", "secret": "owner-secret"}})

    monkeypatch.setattr(runner, "get_json", fake_get_json)
    snapshot = {
        "target": {"base_url": "http://127.0.0.1:5000", "verification_path": "/me", "timeout_seconds": 5},
        "operation": {"path": "/books/{id}", "method": "GET"},
        "resource": {"id": 7, "external_id": "book-1", "resource_type_id": 5, "owner_identity_id": 1, "path_parameter": "id", "resource_id_pointer": "/data/id", "restricted_pointers": ["/data/secret"]},
        "identities": [
            {"id": 1, "role": "reader", "principal_pointer": "/data/username", "expected_principal": "alice"},
            {"id": 2, "role": "reader", "principal_pointer": "/data/username", "expected_principal": "bob"},
        ],
        "policies": [
            {"id": 1, "version": 1, "operation_id": 9, "resource_type_id": 5, "identity_id": 1, "role": None, "resource_id": None, "decision": "ALLOW"},
            {"id": 2, "version": 1, "operation_id": 9, "resource_type_id": 5, "identity_id": 2, "role": None, "resource_id": None, "decision": "DENY"},
        ],
    }
    with session_factory.begin() as session:
        project = Project(name="Lab", description="")
        session.add(project)
        session.flush()
        run = Run(project_id=project.id, status=RunStatus.RUNNING, snapshot=snapshot)
        session.add(run)
        session.flush()
        session.add_all([
            RunIdentitySecret(run_id=run.id, identity_id=1, ciphertext=alice_ciphertext, key_version=1),
            RunIdentitySecret(run_id=run.id, identity_id=2, ciphertext=bob_ciphertext, key_version=1),
        ])

    with session_factory.begin() as session:
        run = session.query(Run).one()
        await runner.execute_run(session, run, settings)

    with session_factory() as session:
        run = session.query(Run).one()
        results = list(session.query(RunResult).order_by(RunResult.case_key))
        findings = list(session.query(Finding))
        reproductions = list(session.query(FindingReproduction))

    assert run.status == RunStatus.COMPLETED
    assert len(results) == 2
    assert results[1].authorization_conclusion == AuthorizationConclusion.CONFIRMED_VIOLATION
    assert results[1].http_status == 403
    assert len(findings) == 1
    assert len(reproductions) == 1
