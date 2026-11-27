"""Isolated SQLite read contracts: no worker lifecycle and no network."""
import copy
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.api.routes import get_session
from backend.app.api.workflow_routes import router
from backend.app.core.auth import require_admin, require_csrf
from backend.app.persistence.database import Base, create_sqlite_engine
from backend.app.persistence.models import (Project, Identity, IdentitySecret, Target,
    OpenApiOperation, OperationResourceMapping, Resource, ResourceType, Policy, Run)
from backend.app.services.demo_presentation import public_snapshot


@pytest.fixture
def contract(tmp_path):
    engine = create_sqlite_engine(tmp_path / 'matrix.sqlite3')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Project(id=1, name='demo'))
        session.flush()
        session.add_all([
            Target(id=1, project_id=1, base_url='http://127.0.0.1:5000', verification_path='/me', request_limit=20),
            ResourceType(id=1, project_id=1, name='item', resource_id_pointer='/id', restricted_pointers=['/secret']),
            *[Identity(id=i, project_id=1, display_name=f'person{i}', role=role, expected_principal='PRINCIPAL_CANARY') for i, role in [(1,'admin'),(2,'reader'),(3,'reader')]],
            *[OpenApiOperation(id=i, project_id=1, operation_key=f'get{i}', method='GET', path=f'/items{i}/{{id}}', selected=True) for i in (1,2)],
        ])
        session.flush()
        session.add_all([
            Resource(id=1, resource_type_id=1, external_id='RESOURCE_CANARY', owner_identity_id=2, path_parameter='id'),
            *[IdentitySecret(identity_id=i, ciphertext='CIPHER_CANARY', key_version=1, fingerprint=str(i)*64) for i in (1,2,3)],
            *[OperationResourceMapping(id=i, project_id=1, operation_id=i, resource_type_id=1, selected=True) for i in (1,2)],
            Policy(id=1, version=3, operation_id=1, resource_type_id=1, identity_id=1, decision='DENY'),
            Run(id=2, project_id=1, status='COMPLETED', snapshot={'resource': {'external_id':'RESOURCE_CANARY'}, 'identities':[{'expected_principal':'PRINCIPAL_CANARY'}], 'secret':'TOKEN_CANARY'}),
        ])
        session.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[require_admin] = lambda: None
        app.dependency_overrides[require_csrf] = lambda: None
        with TestClient(app) as client:
            yield client, session
    engine.dispose()


def test_preview_policy_count_keys_and_redaction(contract):
    client, session = contract
    response = client.get('/api/projects/1/batch-matrix?target_id=1')
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview['actor_case_count'] == len(preview['cases']) == 6
    assert preview['planned_attempts'] == 11
    rows = preview['cases']
    assert len({r['case_key'] for r in rows}) == 6
    assert rows[0]['case_key'] == 'operation:1:resource:1:actor:1'
    assert rows[0]['expected_decision'] == 'DENY'
    assert (rows[0]['policy_id'], rows[0]['policy_version']) == (1,3)
    assert rows[0]['ownership_category'] == 'CROSS_ROLE'
    assert rows[1]['ownership_category'] == 'OWNER'
    assert rows[2]['ownership_category'] == 'CROSS_USER'
    single = client.get('/api/projects/1/matrix?operation_id=1&resource_id=1')
    assert single.json() == rows[:3]
    for url in ('/api/projects/1/resources', '/api/projects/1/runs'):
        result = client.get(url)
        assert result.status_code == 200
        assert not any(c in result.text for c in ('RESOURCE_CANARY','PRINCIPAL_CANARY','TOKEN_CANARY','CIPHER_CANARY'))
    assert session.get(Run,2).snapshot['secret'] == 'TOKEN_CANARY'
    session.get(OperationResourceMapping,1).selected = False
    session.commit()
    assert client.get('/api/projects/1/matrix?operation_id=1&resource_id=1').status_code == 422
    remaining = client.get('/api/projects/1/batch-matrix?target_id=1').json()['cases']
    assert remaining == rows[3:]


def test_invalid_scope_and_unselected_operation(contract):
    client, session = contract
    assert client.get('/api/projects/1/batch-matrix?target_id=999').status_code == 422
    assert client.get('/api/projects/1/matrix?operation_id=999&resource_id=1').status_code == 422
    session.get(OpenApiOperation,1).selected = False
    session.commit()
    assert client.get('/api/projects/1/matrix?operation_id=1&resource_id=1').status_code == 422
    assert client.get('/api/projects/1/batch-matrix?target_id=1').status_code == 422


def test_historical_allowlist_does_not_mutate_unknown_nested_keys():
    raw = {'identities':[{'expected_principal':'CANARY'}], 'resource':{'external_id':'CANARY'},
           'request_plan':{'planned_attempts':5,'ciphertext':'CANARY'}, 'unknown':{'body':'CANARY'}}
    original = copy.deepcopy(raw)
    assert 'CANARY' not in json.dumps(public_snapshot(raw))
    assert public_snapshot(raw)['request_plan'] == {'planned_attempts':5}
    assert raw == original


def test_reorder_and_foreign_scope_planner():
    from backend.tests.test_batch_plan import configuration
    from backend.app.services.batch_plan import build_batch_plan, BatchPlanError
    from backend.app.services.demo_presentation import matrix_rows
    target, identities, secrets, mappings, operations, types, resources = configuration()
    def plan():
        return build_batch_plan(target=target, identities=identities, identity_secrets=secrets,
            mappings=mappings, operations=operations, resource_types=types, resources=resources, policies=[])
    def keys(p):
        return [r['case_key'] for t in p.targets for r in matrix_rows(t.operation,t.resource,p.identities,t.policies)]
    expected = keys(plan())
    identities.reverse()
    resources.reverse()
    assert keys(plan()) == expected
    mappings[0].project_id = 99
    with pytest.raises(BatchPlanError):
        plan()
    mappings[0].project_id = target.project_id
    mappings.append(mappings[0])
    with pytest.raises(BatchPlanError):
        plan()


def test_conflict_and_no_match_are_unknown(contract):
    client, session = contract
    session.add(Policy(id=2,version=1,operation_id=1,resource_type_id=1,identity_id=1,decision='ALLOW'))
    session.commit()
    rows = client.get('/api/projects/1/batch-matrix?target_id=1').json()['cases']
    assert rows[0]['expected_decision'] == 'UNKNOWN'
    assert rows[0]['policy_status'] == 'UNRESOLVED_CONFLICT'
    assert 'policy.unresolved_conflict' in rows[0]['warnings']
    assert rows[1]['policy_status'] == 'NO_MATCH'
    assert rows[1]['policy_id'] is None


def test_resource_edit_preserves_write_only_identifier(contract):
    client, session = contract
    response = client.patch('/api/resources/1', json={'owner_identity_id':2,'path_parameter':'id'})
    assert response.status_code == 200
    assert response.json()['external_id'] == '[REDACTED]'
    assert session.get(Resource,1).external_id == 'RESOURCE_CANARY'
    assert client.patch('/api/resources/1',json={'external_id':'[REDACTED]','owner_identity_id':2,'path_parameter':'id'}).status_code == 422
    assert session.get(Resource,1).external_id == 'RESOURCE_CANARY'
    replacement = client.patch('/api/resources/1', json={'external_id':'REPLACEMENT_CANARY','owner_identity_id':2,'path_parameter':'id'})
    assert replacement.status_code == 200
    assert replacement.json()['external_id'] == '[REDACTED]'
    assert 'REPLACEMENT_CANARY' not in replacement.text
    assert session.get(Resource,1).external_id == 'REPLACEMENT_CANARY'
