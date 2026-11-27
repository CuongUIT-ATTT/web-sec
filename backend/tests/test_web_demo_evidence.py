"""Synthetic evidence regressions; transport is stubbed, never contacts a lab."""
import json
from copy import deepcopy

import pytest
from cryptography.fernet import Fernet

from backend.app.domain.contracts import AuthorizationConclusion as C, ExecutionStatus as E, PolicyDecision as D
from backend.app.persistence.models import Run, RunResult
from backend.app.scanner.classification.evaluator import Observation
from backend.app.scanner.execution.http_client import HttpObservation
from backend.app.workers import runner
from backend.tests.test_evaluator import assess
from backend.tests.test_batch_runner_regressions import _create_run, _settings


@pytest.mark.parametrize('decision,expected', [(D.UNKNOWN, C.INSUFFICIENT_EVIDENCE), (D.ALLOW, C.POLICY_CONSISTENT_CASE), (D.DENY, C.CONFIRMED_VIOLATION)])
def test_explicit_policy_required(decision, expected):
    assert assess(policy_decision=decision).conclusion == expected


@pytest.mark.parametrize('value', [None, '', '   ', [], {}, {'nested': None}, [None]])
def test_empty_owner_restricted_values_never_confirm(value):
    body = {'data': {'id': 'book-2', 'secret': value}}
    assert assess(owner_body=body, observation=Observation(E.COMPLETED_RESPONSE, 200, body)).conclusion == C.INVALID_TEST


def test_nested_equality_and_resource_and_type_guards():
    body = {'data': {'id': 'book-2', 'secret': {'a': [1, 2], 'b': 'canary'}}}
    actor = {'data': {'id': 'book-2', 'secret': {'b': 'canary', 'a': [1, 2]}}}
    assert assess(owner_body=body, observation=Observation(E.COMPLETED_RESPONSE, 403, actor)).conclusion == C.CONFIRMED_VIOLATION
    actor['data']['id'] = 'wrong'
    assert assess(owner_body=body, observation=Observation(E.COMPLETED_RESPONSE, 200, actor)).conclusion == C.INSUFFICIENT_EVIDENCE
    assert not runner.restricted_fields_match({'x': True}, {'x': 1}, ('/x',))


@pytest.mark.asyncio
@pytest.mark.parametrize('batch', [True, False])
@pytest.mark.parametrize('fault', ['none', '403', '500', 'timeout', 'truncated', 'parse', 'wrong_resource', 'null', 'missing', 'principal'])
async def test_persisted_summary_and_owner_guard(monkeypatch, tmp_path, batch, fault):
    key = Fernet.generate_key().decode('ascii')
    factory, run_id = _create_run(tmp_path, key)
    with factory.begin() as session:
        run = session.get(Run, run_id)
        snap = deepcopy(run.snapshot)
        target = snap['targets'][0]
        target['policies'] = [{'id': 10, 'version': 3, 'operation_id': 9, 'resource_type_id': 5,
                               'identity_id': 1, 'role': None, 'resource_id': 7, 'decision': 'DENY'}]
        if not batch:
            snap.pop('run_kind')
            snap.update(target)
        run.snapshot = snap
    calls = 0
    canary = 'SYNTHETIC-SECRET-DO-NOT-PERSIST'
    async def fake_get_json(**kwargs):
        nonlocal calls
        calls += 1
        body = {'data': {'username': 'owner', 'id': 'book-1', 'secret': {'nested': canary}}}
        status, execution, truncated, parse = 200, E.COMPLETED_RESPONSE, False, False
        if calls == 1 and fault == 'principal':
            body['data']['username'] = 'wrong'
        if calls == 2:
            if fault in ('403', '500'): status = int(fault)
            if fault == 'timeout': execution = E.TIMEOUT
            if fault == 'truncated': truncated = True
            if fault == 'parse': parse = True
            if fault == 'wrong_resource': body['data']['id'] = 'other'
            if fault == 'null': body['data']['secret'] = None
            if fault == 'missing': del body['data']['secret']
        if calls == 3: status = 403  # DENY body leakage remains detectable.
        return HttpObservation(execution, status, body, 100, truncated, parse, ())
    monkeypatch.setattr(runner, 'get_json', fake_get_json)
    with factory() as session:
        await runner.execute_run(session, session.get(Run, run_id), _settings(key))
        session.commit()
    with factory() as session:
        result = session.query(RunResult).one()
        metadata = result.response_metadata
        assert result.authorization_conclusion == (C.CONFIRMED_VIOLATION if fault == 'none' else C.INVALID_TEST)
        evidence = metadata['evidence']
        assert evidence['schema_version'] == 2
        assert evidence['actor_role'] == 'reader'
        assert evidence['ownership'] == 'self'
        field = evidence['protected_fields'][0]
        assert field['alias'] == 'protected-1'
        assert field['owner_present'] is (fault != 'missing')
        assert field['matches_owner'] is (fault not in ('null', 'missing'))
        assert evidence['owner_control_valid'] is (fault == 'none')
        assert evidence['run_id'] == run_id
        assert evidence['case_key'] == result.case_key
        assert evidence['policy_id'] == 10 and evidence['policy_version'] == 3
        assert evidence['policy_decision'] == 'DENY'
        assert evidence['policy_resolution'] == 'RESOLVED'
        assert canary not in json.dumps(metadata)
        assert 'test-token' not in json.dumps(metadata)
        assert '/data/' not in json.dumps(metadata)
        assert calls == 3


@pytest.mark.parametrize('body', [{'data': {'id': 'book-2'}}, {'error': 'denied'}, {'data': {'id': 'other', 'secret': 'owner-secret'}}])
def test_public_generic_and_wrong_resource_are_inconclusive(body):
    assert assess(observation=Observation(E.COMPLETED_RESPONSE, 200, body)).conclusion == C.INSUFFICIENT_EVIDENCE


@pytest.mark.parametrize('flag', ['body_truncated', 'parse_error'])
def test_principal_verification_rejects_partial_evidence(flag):
    identity = {'principal_pointer': '/user', 'expected_principal': 'owner'}
    observation = HttpObservation(E.COMPLETED_RESPONSE, 200, {'user': 'owner'}, 1,
                                  flag == 'body_truncated', flag == 'parse_error', ())
    assert not runner._principal_matches(identity, observation)


@pytest.mark.asyncio
@pytest.mark.parametrize('sharing', [False, True])
@pytest.mark.parametrize('owner_role', ['reader', 'admin', None])
async def test_cross_user_and_authorized_sharing(monkeypatch, tmp_path, sharing, owner_role):
    from backend.app.core.secrets import SecretBox
    from backend.app.persistence.models import RunIdentitySecret
    key = Fernet.generate_key().decode('ascii')
    factory, run_id = _create_run(tmp_path, key)
    with factory.begin() as session:
        run = session.get(Run, run_id)
        snap = deepcopy(run.snapshot)
        snap['identities'].append({'id': 2, 'role': 'reader', 'principal_pointer': '/data/username', 'expected_principal': 'other'})
        if owner_role is None:
            snap['identities'][0].pop('role', None)
        else:
            snap['identities'][0]['role'] = owner_role
        snap['target']['request_limit'] = 5
        snap['request_plan'] = {'identity_verifications': 2, 'owner_baselines': 1, 'actor_cases': 2, 'planned_attempts': 5}
        snap['targets'][0]['policies'] = [dict(id=i, version=1, operation_id=9, resource_type_id=5, identity_id=i, role=None, resource_id=7,
            decision='ALLOW' if i == 1 or sharing else 'DENY') for i in (1, 2)]
        run.snapshot = snap
        ciphertext, _ = SecretBox.from_key(key).encrypt_bearer('other-test-token')
        session.add(RunIdentitySecret(run_id=run_id, identity_id=2, ciphertext=ciphertext, key_version=1))
    calls = 0
    async def fake_get_json(**kwargs):
        nonlocal calls
        calls += 1
        body = {'data': {'username': 'other' if calls == 2 else 'owner', 'id': 'book-1', 'secret': 'synthetic-canary'}}
        return HttpObservation(E.COMPLETED_RESPONSE, 200, body, 1, False, False, ())
    monkeypatch.setattr(runner, 'get_json', fake_get_json)
    with factory() as session:
        await runner.execute_run(session, session.get(Run, run_id), _settings(key))
        session.commit()
    with factory() as session:
        results = list(session.query(RunResult).order_by(RunResult.case_key))
        assert results[0].authorization_conclusion == C.POLICY_CONSISTENT_CASE
        assert results[1].authorization_conclusion == (C.POLICY_CONSISTENT_CASE if sharing else C.CONFIRMED_VIOLATION)
        evidence = results[1].response_metadata['evidence']
        assert evidence['owner_role'] == owner_role
        assert evidence['ownership'] == ('unknown' if owner_role is None else 'same-role-other' if owner_role == 'reader' else 'cross-role')
        assert evidence['actor_identity_id'] == 2
        assert 'synthetic-canary' not in json.dumps(results[1].response_metadata)
        assert calls == 5


def test_v2_dto_redaction_and_binding():
    from backend.app.api.workflow_routes import _result_metadata
    from backend.tests.test_web_demo_contracts import evidence_payload
    payload = evidence_payload() | dict(schema_version=2, actor_role='reader', owner_role=None,
                                       ownership='unknown', protected_fields=[dict(alias='protected-1',
                                       owner_present=True, actor_present=False, owner_type='dict',
                                       actor_type=None, matches_owner=False, value='SECRET-CANARY')])
    result = RunResult(run_id=1, case_key=payload['case_key'], response_metadata={'evidence': payload})
    safe = _result_metadata(result).model_dump()
    assert safe['evidence']['ownership'] == 'unknown'
    assert safe['evidence']['owner_role'] is None
    assert 'SECRET-CANARY' not in json.dumps(safe)
    payload['protected_fields'][0]['alias'] = '/private/SECRET-CANARY'
    assert _result_metadata(result).evidence is None
    payload['protected_fields'] = []
    payload['run_id'] = 99
    assert _result_metadata(result).evidence is None
