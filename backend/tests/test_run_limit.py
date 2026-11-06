import ipaddress
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.app.core.secrets import SecretBox
from backend.app.core.settings import Settings
from backend.app.domain.contracts import AuthorizationConclusion, RunStatus
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import Project, Run, RunIdentitySecret, RunResult
from backend.app.workers.runner import execute_run


@pytest.mark.asyncio
async def test_request_limit_blocks_dispatch_before_any_http_call(monkeypatch, tmp_path) -> None:
    key = Fernet.generate_key().decode("ascii")
    settings = Settings(Path("unused.sqlite3"), "password", "s" * 32, key, (ipaddress.ip_network("127.0.0.1/32"),), frozenset({5000}), 32768, 5.0)
    box = SecretBox.from_key(key)
    ciphertext, _ = box.encrypt_bearer("token")
    calls = 0

    async def forbidden_call(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be reached")

    monkeypatch.setattr("backend.app.workers.runner.get_json", forbidden_call)
    snapshot = {
        "target": {"base_url": "http://127.0.0.1:5000", "verification_path": "/me", "timeout_seconds": 5, "request_limit": 1},
        "operation": {"path": "/books/{id}", "method": "GET"},
        "resource": {"id": 1, "external_id": "book", "resource_type_id": 1, "owner_identity_id": 1, "path_parameter": "id", "resource_id_pointer": "/data/id", "restricted_pointers": ["/data/secret"]},
        "identities": [{"id": 1, "role": "reader", "principal_pointer": "/data/name", "expected_principal": "alice"}],
        "policies": [],
    }
    session_factory = create_session_factory(tmp_path / "app.sqlite3")
    with session_factory.begin() as session:
        project = Project(name="Lab", description="")
        session.add(project)
        session.flush()
        run = Run(project_id=project.id, status=RunStatus.RUNNING, snapshot=snapshot)
        session.add(run)
        session.flush()
        session.add(RunIdentitySecret(run_id=run.id, identity_id=1, ciphertext=ciphertext, key_version=1))

    with session_factory.begin() as session:
        await execute_run(session, session.query(Run).one(), settings)

    with session_factory() as session:
        result = session.query(RunResult).one()

    assert calls == 0
    assert result.authorization_conclusion == AuthorizationConclusion.NOT_EVALUATED
    assert result.reason_codes == ["execution.request_limit_reached"]
