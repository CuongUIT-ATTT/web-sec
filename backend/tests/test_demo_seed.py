"""Main-web seed, immutable history and actual GET evidence on isolated SQLite."""
import asyncio
import ipaddress
import json
import threading
from dataclasses import replace
from http.server import ThreadingHTTPServer

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.persistence.models import Project, Run, Target, Identity, IdentityVerification, ProjectAuthorizationRevision
from backend.app.services.demo_seed import seed_demo, NAME
from backend.app.workers.runner import execute_run
from deploy.synthetic_lab import Handler


@pytest.fixture
def demo(tmp_path, monkeypatch):
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings = Settings(database_path=tmp_path/'demo.sqlite', admin_password='test-only',
        session_secret='s'*32, secret_encryption_key=Fernet.generate_key().decode(),
        target_networks=(ipaddress.ip_network('127.0.0.1/32'),), allowed_ports=frozenset({server.server_port}),
        max_response_bytes=32768, default_timeout_seconds=2,
        demo_target_url=f'http://127.0.0.1:{server.server_port}')
    async def stopped_worker(factory, settings, stop):
        await stop.wait()
    monkeypatch.setattr('backend.app.main.worker_loop', stopped_worker)
    app = create_app(settings)
    with TestClient(app) as client:
        yield client, app, settings
    server.shutdown()
    server.server_close()
    thread.join()


def login(client):
    return {'X-CSRF-Token': client.post('/api/auth/login', json={'password':'test-only'}).json()['csrf_token']}


def test_seed_actual_get_matrix_run_results_and_idempotence(demo):
    client, app, settings = demo
    assert client.post('/api/demo/seed').status_code == 401
    headers = login(client)
    assert client.post('/api/demo/seed').status_code == 403
    with app.state.session_factory() as s:
        p = Project(name='Existing project', description='preserve')
        s.add(p); s.flush()
        legacy = Run(project_id=p.id, status='COMPLETED', snapshot={'evidence':'immutable'})
        s.add(legacy); s.commit()
        legacy_id = legacy.id
    seeded = client.post('/api/demo/seed', headers=headers)
    assert seeded.status_code == 200, seeded.text
    assert seeded.json()['created'] is True
    pid = seeded.json()['project_id']
    target = client.get(f'/api/projects/{pid}/targets').json()[0]
    with app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Run)) == 1  # no scanner queued
        checks = list(s.scalars(select(IdentityVerification)))
        assert len(checks) == 3 and all(c.authentication_passed and c.principal_matched for c in checks)
    root = f'/api/projects/{pid}/authorization'
    preview = client.get(root+f'/preview?target_id={target["id"]}').json()
    assert preview['identity_count'] == 3
    assert preview['actor_case_count'] == preview['executable_case_count'] == 12
    assert not preview['exclusions']
    assert {c['kind'] for c in preview['cases']} == {'BOLA','BFLA'}
    queued = client.post(root+'/runs', headers=headers, json={
        'target_id':target['id'], 'policy_revision':preview['policy_revision'],
        'case_ids':[c['case_id'] for c in preview['cases']]})
    assert queued.status_code == 201, queued.text
    rid = queued.json()['id']
    with app.state.session_factory() as s:
        from backend.app.workers.queue import claim_next_run
        run = claim_next_run(s)
        assert run.id == rid
        s.commit()
        asyncio.run(execute_run(s, run, settings))
        s.commit()
        snapshot = json.dumps(run.snapshot, sort_keys=True)
        revision_before = s.scalar(select(ProjectAuthorizationRevision)).configuration
    results = client.get(root+f'/runs/{rid}/results').json()
    assert results['status'] == 'COMPLETED', results
    assert len(results['cases']) == 12
    assert all(c['http_status'] == 200 for c in results['cases'])
    denied = [c for c in results['cases'] if c['expected_decision']=='DENY']
    assert len(denied) == 6
    assert all(c['conclusion']=='CONFIRMED_VIOLATION' for c in denied), denied
    again = client.post('/api/demo/seed', headers=headers).json()
    assert again == dict(project_id=pid, created=False, synthetic=True)
    assert client.get(root+f'/runs/{rid}/results').json() == results
    with app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Project)) == 2
        assert s.scalar(select(func.count()).select_from(Identity)) == 3
        assert s.scalar(select(func.count()).select_from(IdentityVerification)) == 3
        assert s.scalar(select(func.count()).select_from(Run)) == 2
        assert s.get(Run, legacy_id).snapshot == {'evidence':'immutable'}
        assert json.dumps(s.get(Run,rid).snapshot, sort_keys=True) == snapshot
        assert s.scalar(select(ProjectAuthorizationRevision)).configuration == revision_before


def test_seed_fail_closed_disabled_scope_collision_and_unreachable(demo):
    client, app, settings = demo
    headers = login(client)
    for changed in (replace(settings, demo_target_url=''), replace(settings, allowed_ports=frozenset({1}))):
        app.state.settings = changed
        assert client.post('/api/demo/seed', headers=headers).status_code == 409
    app.state.settings = settings
    with app.state.session_factory() as s:
        s.add(Project(name=NAME, description='user project'))
        s.commit()
    assert client.post('/api/demo/seed', headers=headers).status_code == 409
    with app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Target)) == 0
        assert s.scalar(select(Project)).description == 'user project'


def test_seed_no_fabricated_verification_when_target_unreachable(demo):
    client, app, settings = demo
    # Port 1 is closed in this isolated local test; no external API is used.
    app.state.settings = replace(settings, demo_target_url='http://127.0.0.1:1', allowed_ports=frozenset({1}))
    response = client.post('/api/demo/seed', headers=login(client))
    assert response.status_code == 200
    pid = response.json()['project_id']
    tid = client.get(f'/api/projects/{pid}/targets').json()[0]['id']
    preview = client.get(f'/api/projects/{pid}/authorization/preview?target_id={tid}').json()
    assert preview['executable_case_count'] == 0
    assert len(preview['exclusions']) == 3
    with app.state.session_factory() as s:
        assert all(not c.authentication_passed for c in s.scalars(select(IdentityVerification)))
        assert s.scalar(select(func.count()).select_from(Run)) == 0


def test_concurrent_seed_calls_and_operator_edits_are_preserved(demo):
    from concurrent.futures import ThreadPoolExecutor
    client, app, settings = demo
    def seed_once(_):
        with app.state.session_factory() as s:
            project, created = seed_demo(s, settings)
            return project.id, created
    with ThreadPoolExecutor(max_workers=2) as pool:
        calls = list(pool.map(seed_once, range(2)))
    assert calls[0][0] == calls[1][0]
    assert sorted(created for _, created in calls) == [False, True]
    with app.state.session_factory() as s:
        row = s.scalar(select(ProjectAuthorizationRevision))
        row.configuration = {'rules':[], 'operations':[], 'sharing':[]}
        target = s.scalar(select(Target))
        target.request_limit = 7
        s.commit()
    assert seed_once(0) == (calls[0][0], False)
    with app.state.session_factory() as s:
        assert s.scalar(select(ProjectAuthorizationRevision)).configuration == {'rules':[], 'operations':[], 'sharing':[]}
        assert s.scalar(select(Target)).request_limit == 7
        assert s.scalar(select(func.count()).select_from(Project)) == 1


def test_duplicate_fixture_token_rolls_back_without_leaking_ciphertext(demo):
    from backend.app.core.secrets import SecretBox
    from backend.app.persistence.models import IdentitySecret
    client, app, settings = demo
    with app.state.session_factory() as s:
        p = Project(name='Operator project')
        s.add(p); s.flush()
        actor = Identity(project_id=p.id, display_name='existing')
        s.add(actor); s.flush()
        encrypted, digest = SecretBox.from_key(settings.secret_encryption_key).encrypt_bearer('t18-synthetic-v1-userA')
        s.add(IdentitySecret(identity_id=actor.id, ciphertext=encrypted, fingerprint=digest))
        s.commit()
    response = client.post('/api/demo/seed', headers=login(client))
    assert response.status_code == 409
    assert encrypted not in response.text and digest not in response.text
    with app.state.session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Project)) == 1
        assert s.scalar(select(func.count()).select_from(Target)) == 0


def test_synthetic_lab_rejects_invalid_tokens_and_writes(demo):
    import httpx
    _, _, settings = demo
    with httpx.Client(base_url=settings.demo_target_url, trust_env=False) as client:
        assert client.get('/me').status_code == 401
        assert client.get('/me', headers={'Authorization':'userA'}).status_code == 401
        assert client.get('/me', headers={'Authorization':'Bearer invalid'}).status_code == 401
        assert client.get('/me', headers={'Authorization':'Bearer t18-synthetic-v1-userA'}).json()['id'] == 'userA'
        assert client.post('/books/userA-book').status_code == 501
        assert client.delete('/books/userA-book').status_code == 501


def test_ssh_profile_migration_preserves_secrets_history_and_is_idempotent(demo):
    from backend.app.services.ssh_seed import seed_ssh
    from backend.app.services.authorization_model import AuthorizationConfig, preview
    from backend.app.persistence.models import IdentitySecret, Resource, ResourceType, OpenApiOperation
    client, app, settings = demo
    pid = client.post('/api/demo/seed', headers=login(client)).json()['project_id']
    scoped = replace(settings, target_networks=(ipaddress.ip_network('100.106.64.21/32'),), allowed_ports=frozenset({5003}))
    with app.state.session_factory() as s:
        secrets = [(r.identity_id, r.ciphertext, r.fingerprint) for r in s.scalars(select(IdentitySecret))]
        old_checks = s.scalar(select(func.count()).select_from(IdentityVerification))
        old_revision = s.scalar(select(ProjectAuthorizationRevision)).configuration
        run = Run(project_id=pid, status='COMPLETED', snapshot={'immutable':'ssh-migration'})
        s.add(run); s.commit()
        run_id = run.id
        project, target = seed_ssh(s, scoped, project_id=pid)
        s.commit()
        assert target.base_url == 'http://100.106.64.21:5003'
        assert [(r.identity_id, r.ciphertext, r.fingerprint) for r in s.scalars(select(IdentitySecret))] == secrets
        assert s.get(Run, run_id).snapshot == {'immutable':'ssh-migration'}
        assert s.scalar(select(ProjectAuthorizationRevision).order_by(ProjectAuthorizationRevision.id)).configuration == old_revision
        checks = list(s.scalars(select(IdentityVerification).order_by(IdentityVerification.id)))
        assert len(checks) == old_checks + 3
        assert all(c.execution_status == 'NOT_RUN' for c in checks[-3:])
        latest = s.scalar(select(ProjectAuthorizationRevision).order_by(ProjectAuthorizationRevision.id.desc()))
        config = AuthorizationConfig.model_validate(latest.configuration)
        assert len(config.rules) == 1 and config.rules[0].decision == 'ALLOW'
        ops = list(s.scalars(select(OpenApiOperation).where(OpenApiOperation.selected.is_(True))))
        assert [o.path for o in ops] == ['/books/{book_id}']
        rt = s.scalar(select(ResourceType).where(ResourceType.name == 'ssh-book'))
        assert rt.resource_id_pointer == '/data/id' and rt.restricted_pointers == ['/data/secret']
        resources = list(s.scalars(select(Resource).where(Resource.resource_type_id == rt.id)))
        owners = {a.id:a.display_name for a in s.scalars(select(Identity))}
        assert {(r.external_id, owners[r.owner_identity_id], r.path_parameter) for r in resources} == {
            (f'book-{p}{i}', name, 'book_id') for p,name in [('A','userA'),('B','userB')] for i in [1,2]}
        assert preview(s, pid, target, config)['executable_case_count'] == 0
        # Simulated verification rows test matrix policy logic only, no live claim.
        for actor in s.scalars(select(Identity)):
            assert actor.principal_pointer == '/principal/username'
            s.add(IdentityVerification(identity_id=actor.id, target_id=target.id,
                authentication_passed=True, principal_matched=True, execution_status='COMPLETED_RESPONSE'))
        s.commit()
        matrix = preview(s, pid, target, config)
        assert matrix['executable_case_count'] == 4
        assert len(matrix['cases']) == 12
        unknown = [c for c in matrix['cases'] if c['expected_decision'] == 'UNKNOWN']
        assert len(unknown) == 8 and all('UNKNOWN_POLICY' in c['reasons'] for c in unknown)
        assert all(c['baseline_identity_id'] == c['owner_identity_id'] for c in matrix['cases'])
        count_checks = s.scalar(select(func.count()).select_from(IdentityVerification))
        s.commit()
        seed_ssh(s, scoped, project_id=pid); s.commit()
        assert s.scalar(select(func.count()).select_from(IdentityVerification)) == count_checks
        assert s.scalar(select(func.count()).select_from(ProjectAuthorizationRevision)) == 2


def test_ssh_profile_creation_has_no_fake_credentials_and_refuses_active_run(demo):
    from backend.app.services.ssh_seed import seed_ssh
    from backend.app.persistence.models import IdentitySecret
    _, app, settings = demo
    scoped = replace(settings, target_networks=(ipaddress.ip_network('100.106.64.21/32'),), allowed_ports=frozenset({5003}))
    with app.state.session_factory() as s:
        project, _ = seed_ssh(s, scoped); s.commit()
        assert s.scalar(select(func.count()).select_from(IdentitySecret)) == 0
        pid = project.id
        s.add(Run(project_id=pid, status='RUNNING', snapshot={})); s.commit()
        with pytest.raises(ValueError, match='run'):
            seed_ssh(s, scoped, project_id=pid)
        s.rollback()


def test_ssh_profile_rejects_out_of_scope_and_unrelated_project(demo):
    from backend.app.services.ssh_seed import seed_ssh
    _, app, settings = demo
    with app.state.session_factory() as s:
        with pytest.raises(ValueError):
            seed_ssh(s, settings)
        s.rollback()
        assert s.scalar(select(func.count()).select_from(Project)) == 0
        p = Project(name='operator-owned', description='preserve')
        s.add(p); s.commit()
        scoped = replace(settings, target_networks=(ipaddress.ip_network('100.106.64.21/32'),), allowed_ports=frozenset({5003}))
        with pytest.raises(ValueError, match='dự án mẫu'):
            seed_ssh(s, scoped, project_id=p.id)
        s.rollback()
        assert s.scalar(select(func.count()).select_from(Target)) == 0


def test_ssh_seed_button_contract_preserves_edits_and_never_calls_lab(demo, monkeypatch):
    from backend.app.persistence.models import Resource, IdentitySecret, ResourceType
    client, app, settings = demo
    assert client.post('/api/demo/ssh-seed').status_code == 401
    headers = login(client)
    assert client.post('/api/demo/ssh-seed').status_code == 403
    assert client.post('/api/demo/ssh-seed', headers=headers).status_code == 409
    app.state.settings = replace(settings, target_networks=(ipaddress.ip_network('100.106.64.21/32'),), allowed_ports=frozenset({5003}))
    async def forbidden(*args, **kwargs):
        pytest.fail('Seed must not verify identities or call lab')
    monkeypatch.setattr('backend.app.api.demo_routes.verify_identity', forbidden)
    response = client.post('/api/demo/ssh-seed', headers=headers)
    assert response.status_code == 200, response.text
    pid = response.json()['project_id']
    assert response.json() == dict(project_id=pid, created=True, synthetic=False)
    with app.state.session_factory() as s:
        assert s.scalar(select(Target)).base_url == 'http://100.106.64.21:5003'
        actors = {a.id: a.display_name for a in s.scalars(select(Identity))}
        assert set(actors.values()) == {'userA', 'userB', 'admin'}
        assert {(r.external_id, actors[r.owner_identity_id], r.path_parameter) for r in s.scalars(select(Resource))} == {
            ('book-A1', 'userA', 'book_id'), ('book-A2', 'userA', 'book_id'),
            ('book-B1', 'userB', 'book_id'), ('book-B2', 'userB', 'book_id')}
        kind = s.scalar(select(ResourceType))
        assert (kind.resource_id_pointer, kind.restricted_pointers) == ('/data/id', ['/data/secret'])
        assert s.scalar(select(func.count()).select_from(IdentitySecret)) == 0
        assert s.scalar(select(func.count()).select_from(Run)) == 0
        target = s.scalar(select(Target)); target.request_limit = 7
        policy = s.scalar(select(ProjectAuthorizationRevision)); policy.configuration = {'operator': 'preserve'}
        s.commit()
    assert client.post('/api/demo/ssh-seed', headers=headers).json() == dict(project_id=pid, created=False, synthetic=False)
    with app.state.session_factory() as s:
        assert s.scalar(select(Target)).request_limit == 7
        assert s.scalar(select(ProjectAuthorizationRevision)).configuration == {'operator': 'preserve'}
        assert s.scalar(select(func.count()).select_from(Project)) == 1
