"""Explicit reveal uses persisted configuration, with no lab traffic."""
import ipaddress
from dataclasses import replace

from sqlalchemy import select
from backend.tests.test_demo_seed import demo, login
from backend.app.persistence.models import Resource, Identity, Project, OpenApiOperation
from backend.app.workers.runner import _concrete_path


def test_inspection_requires_session_csrf_and_project_scope(demo):
    client, app, settings = demo
    app.state.settings = replace(settings, target_networks=(ipaddress.ip_network('100.106.64.21/32'),), allowed_ports=frozenset({5003}))
    url = '/api/projects/1/resources/1/inspect'
    assert client.post(url).status_code == 401
    headers = login(client)
    pid = client.post('/api/demo/ssh-seed', headers=headers).json()['project_id']
    resources = client.get(f'/api/projects/{pid}/resources').json()
    assert len(resources) == 4
    assert all(r['external_id'] == '[REDACTED]' for r in resources)
    with app.state.session_factory() as session:
        names = {i.id: i.display_name for i in session.scalars(select(Identity))}
        session.add(Project(id=99, name='other'))
        session.commit()
    observed = set()
    for r in resources:
        url = f'/api/projects/{pid}/resources/{r["id"]}/inspect'
        assert client.post(url).status_code == 403
        assert client.get(url).status_code == 405
        assert client.post(f'/api/projects/99/resources/{r["id"]}/inspect', headers=headers).status_code == 404
        response = client.post(url, headers=headers)
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        data = response.json()
        observed.add((data['external_id'], names[data['owner_identity_id']], data['path_parameter']))
        assert data['request_previews'][0]['path'] == _concrete_path('/books/{book_id}', 'book_id', data['external_id'])
        assert set(data) == {'id','resource_type_id','external_id','resource_alias','owner_identity_id','path_parameter','request_previews'}
    assert observed == {('book-A1','userA','book_id'), ('book-A2','userA','book_id'), ('book-B1','userB','book_id'), ('book-B2','userB','book_id')}
    # Saving and reading in a new request/session must use the persisted ID.
    rid = resources[0]['id']
    updated = client.patch(f'/api/resources/{rid}', headers=headers, json={
        'external_id':'book /?#%', 'owner_identity_id':resources[0]['owner_identity_id'], 'path_parameter':'book_id'})
    assert updated.json()['external_id'] == '[REDACTED]'
    url = f'/api/projects/{pid}/resources/{rid}/inspect'
    for _ in range(2):
        data = client.post(url, headers=headers).json()
        assert data['external_id'] == 'book /?#%'
        assert data['request_previews'][0]['path'] == '/books/book%20%2F%3F%23%25'
    with app.state.session_factory() as session:
        operation = session.scalar(select(OpenApiOperation))
        operation.selected = False
        session.commit()
    assert client.post(url, headers=headers).json()['request_previews'] == []
    assert all(r['external_id'] == '[REDACTED]' for r in client.get(f'/api/projects/{pid}/resources').json())
