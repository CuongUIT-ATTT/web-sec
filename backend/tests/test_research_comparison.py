"""Read-only comparison against synthetic SQLite; no runner, CLI or lab."""
from copy import deepcopy
import pytest
from backend.tests.test_web_demo_contracts import contract, evidence_payload
from backend.app.persistence.models import Run, RunResult


def add_result(session, run_id, key, evidence=None):
    row = RunResult(run_id=run_id, case_key=key, execution_status='COMPLETED_RESPONSE',
                    authorization_conclusion='CONFIRMED_VIOLATION', http_status=403,
                    response_metadata={'evidence': evidence, 'body': 'SECRET-CANARY'})
    session.add(row)
    session.commit()
    return row


def test_exact_run_case_and_redaction(contract):
    client, session = contract
    snapshot = {'external_id': 'SECRET-CANARY', 'policies': [{'version': 999}]}
    session.add_all([Run(id=1, project_id=1, snapshot=deepcopy(snapshot)), Run(id=2, project_id=1), Run(id=3, project_id=2)])
    session.commit()
    e = evidence_payload() | {'raw_body': 'SECRET-CANARY'}
    add_result(session, 1, e['case_key'], e)
    add_result(session, 1, 'operation:1:' + e['case_key'], e)  # no legacy/canonical guessing
    add_result(session, 2, e['case_key'], e)  # no cross-run join
    add_result(session, 3, 'FOREIGN-CANARY')
    response = client.get('/api/projects/1/runs/1/comparison')
    assert response.status_code == 200
    payload = response.json()
    assert payload['run_id'] == 1 and len(payload['cases']) == 2
    for case in payload['cases']:
        assert case['run_id'] == 1
        manual, t18, zap = case['methods']
        assert manual['execution_status'] == zap['execution_status'] == 'NOT_RUN'
        assert manual['provenance'] == zap['artifact'] == 'UNAVAILABLE'
        assert t18['provenance'].startswith('run:1:result:')
        assert t18['timing_status'] == 'TIMING_NOT_AVAILABLE'
        assert t18['observation']['http_status'] == 403
    assert payload['cases'][0]['methods'][1]['observation']['response_metadata']['evidence']['policy_version'] == 7
    assert payload['cases'][1]['methods'][1]['observation']['response_metadata']['evidence'] is None
    assert 'SECRET-CANARY' not in response.text and 'FOREIGN-CANARY' not in response.text
    assert session.get(Run, 1).snapshot == snapshot
    assert client.get('/api/projects/1/runs/3/comparison').status_code == 404
    assert client.get('/api/projects/1/runs/99/comparison').status_code == 404


def test_empty_and_missing_provenance(contract):
    client, session = contract
    session.add(Run(id=1, project_id=1))
    session.commit()
    assert client.get('/api/projects/1/runs/1/comparison').json()['cases'] == []
    add_result(session, 1, None)
    row = client.get('/api/projects/1/runs/1/comparison').json()['cases'][0]
    assert row['case_key'] is None
    assert row['methods'][1]['observation']['response_metadata']['evidence'] is None
    assert row['methods'][1]['artifact'] == 'UNAVAILABLE'


@pytest.mark.parametrize('field,value', [('run_id', 2), ('case_key', 'another-case')])
def test_mismatched_evidence_unavailable(contract, field, value):
    client, session = contract
    session.add(Run(id=1, project_id=1))
    session.commit()
    e = evidence_payload()
    add_result(session, 1, e['case_key'], e | {field: value})
    assert client.get('/api/projects/1/runs/1/comparison').json()['cases'][0]['methods'][1]['observation']['response_metadata']['evidence'] is None
