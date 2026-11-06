import ipaddress
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.app.core.secrets import SecretBox
from backend.app.core.settings import Settings
from backend.app.domain.contracts import AuthorizationConclusion, ExecutionStatus, RunStatus
from backend.app.persistence.database import create_session_factory
from backend.app.persistence.models import BatchCaseClaim, Project, Run, RunExecutionStats, RunIdentitySecret, RunResult
from backend.app.scanner.execution.http_client import HttpObservation
from backend.app.workers import runner
from backend.app.workers.queue import interrupt_orphaned_runs, request_cancellation


def _settings(key: str) -> Settings:
    return Settings(
        Path("unused.sqlite3"), "password", "s" * 32, key,
        (ipaddress.ip_network("127.0.0.1/32"),), frozenset({5000}), 32768, 5.0,
    )


def _snapshot() -> dict[str, object]:
    return {
        "schema_version": 2,
        "run_kind": "BATCH_ALL_SELECTED",
        "target": {
            "base_url": "http://127.0.0.1:5000",
            "verification_path": "/me",
            "timeout_seconds": 5,
            "request_limit": 3,
        },
        "request_plan": {
            "identity_verifications": 1,
            "owner_baselines": 1,
            "actor_cases": 1,
            "planned_attempts": 3,
        },
        "identities": [{
            "id": 1,
            "role": "reader",
            "principal_pointer": "/data/username",
            "expected_principal": "owner",
        }],
        "targets": [{
            "operation": {"id": 9, "path": "/books/{id}", "method": "GET"},
            "resource": {
                "id": 7,
                "external_id": "book-1",
                "resource_type_id": 5,
                "owner_identity_id": 1,
                "path_parameter": "id",
                "resource_id_pointer": "/data/id",
                "restricted_pointers": ["/data/secret"],
            },
            "policies": [],
        }],
    }


def _completed_observation() -> HttpObservation:
    return HttpObservation(
        ExecutionStatus.COMPLETED_RESPONSE, 200,
        {"data": {"username": "owner", "id": "book-1", "secret": "test"}},
        1, False, False, (),
    )


def _create_run(tmp_path, key: str):
    box = SecretBox.from_key(key)
    ciphertext, _ = box.encrypt_bearer("test-token")
    factory = create_session_factory(tmp_path / "batch-regressions.sqlite3")
    with factory.begin() as session:
        project = Project(name="lab", description="")
        session.add(project)
        session.flush()
        run = Run(project_id=project.id, status=RunStatus.RUNNING, snapshot=_snapshot())
        session.add(run)
        session.flush()
        session.add(RunIdentitySecret(run_id=run.id, identity_id=1, ciphertext=ciphertext, key_version=1))
        run_id = run.id
    return factory, run_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "counter"),
    [
        (ExecutionStatus.SCOPE_BLOCKED, "scope_blocked"),
        (ExecutionStatus.TIMEOUT, "transport_errors"),
        (ExecutionStatus.NETWORK_ERROR, "transport_errors"),
    ],
)
async def test_batch_accounting_buckets_each_non_response_outcome(monkeypatch, tmp_path, outcome, counter) -> None:
    key = Fernet.generate_key().decode("ascii")
    factory, run_id = _create_run(tmp_path, key)
    calls = 0

    async def fake_get_json(**kwargs) -> HttpObservation:
        nonlocal calls
        calls += 1
        return HttpObservation(outcome, None, None, 0, False, False, ())

    monkeypatch.setattr(runner, "get_json", fake_get_json)
    with factory() as session:
        assert await runner.execute_run(session, session.get(Run, run_id), _settings(key)) is True
        session.commit()

    with factory() as session:
        run = session.get(Run, run_id)
        stats = session.query(RunExecutionStats).one()
        result = session.query(RunResult).one()

    assert run.status == RunStatus.COMPLETED
    assert calls == stats.planned_attempts == stats.transport_attempts == 3
    assert stats.completed_responses == 0
    assert stats.scope_blocked == (3 if counter == "scope_blocked" else 0)
    assert stats.transport_errors == (3 if counter == "transport_errors" else 0)
    assert stats.transport_attempts == stats.completed_responses + stats.scope_blocked + stats.transport_errors
    assert result.authorization_conclusion != AuthorizationConclusion.CONFIRMED_VIOLATION


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_on_call", [1, 2, 3])
async def test_batch_cancellation_stops_later_dispatch_and_finalizes(monkeypatch, tmp_path, cancel_on_call) -> None:
    key = Fernet.generate_key().decode("ascii")
    factory, run_id = _create_run(tmp_path, key)
    calls: list[int] = []

    async def fake_get_json(**kwargs) -> HttpObservation:
        calls.append(len(calls) + 1)
        if len(calls) == cancel_on_call:
            with factory.begin() as cancellation_session:
                assert request_cancellation(cancellation_session, run_id) is True
        return _completed_observation()

    monkeypatch.setattr(runner, "get_json", fake_get_json)
    with factory() as session:
        assert await runner.execute_run(session, session.get(Run, run_id), _settings(key)) is True
        session.commit()

    with factory() as session:
        run = session.get(Run, run_id)
        stats = session.query(RunExecutionStats).one()
        results = list(session.query(RunResult).order_by(RunResult.case_key))
        claims = list(session.query(BatchCaseClaim))

    assert run.status == RunStatus.CANCELLED
    assert calls == list(range(1, cancel_on_call + 1))
    assert stats.transport_attempts == cancel_on_call
    assert stats.transport_attempts == stats.completed_responses + stats.scope_blocked + stats.transport_errors
    assert len(results) == len(claims) == 1
    if cancel_on_call < 3:
        assert results[0].execution_status == ExecutionStatus.CANCELLED
        assert results[0].authorization_conclusion == AuthorizationConclusion.NOT_EVALUATED
        assert stats.cancelled_cases == 1
    else:
        assert results[0].execution_status == ExecutionStatus.COMPLETED_RESPONSE
        assert stats.cancelled_cases == 0


@pytest.mark.asyncio
async def test_post_dispatch_crash_interrupts_without_replay_or_evidence_rewrite(monkeypatch, tmp_path) -> None:
    key = Fernet.generate_key().decode("ascii")
    factory, run_id = _create_run(tmp_path, key)
    dispatched = False
    original_flush = None

    async def fake_get_json(**kwargs) -> HttpObservation:
        nonlocal dispatched
        dispatched = True
        return _completed_observation()

    monkeypatch.setattr(runner, "get_json", fake_get_json)
    with factory() as session:
        original_flush = session.flush

        def crash_after_dispatch(*args, **kwargs):
            if dispatched:
                raise RuntimeError("injected post-dispatch persistence crash")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(session, "flush", crash_after_dispatch)
        with pytest.raises(RuntimeError, match="post-dispatch"):
            await runner.execute_run(session, session.get(Run, run_id), _settings(key))
        session.rollback()

    with factory.begin() as session:
        assert interrupt_orphaned_runs(session) == 1

    replay_calls = 0

    async def replay_probe(**kwargs) -> HttpObservation:
        nonlocal replay_calls
        replay_calls += 1
        return _completed_observation()

    monkeypatch.setattr(runner, "get_json", replay_probe)
    with factory.begin() as session:
        assert await runner.execute_run(session, session.get(Run, run_id), _settings(key)) is False

    with factory() as session:
        run = session.get(Run, run_id)
        stats = session.query(RunExecutionStats).one()
        results = session.query(RunResult).count()
        claims = session.query(BatchCaseClaim).count()

    assert dispatched is True
    assert run.status == RunStatus.INTERRUPTED
    assert replay_calls == 0
    assert results == claims == 0
    # The pre-dispatch checkpoint is durable; only the post-response bucket is lost.
    assert (stats.transport_attempts, stats.completed_responses) == (1, 0)
