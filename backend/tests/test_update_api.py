import ipaddress

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app
from backend.app.persistence.models import IdentitySecret, Run


def settings_for(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "app.sqlite3",
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key=Fernet.generate_key().decode("ascii"),
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32768,
        default_timeout_seconds=5.0,
    )


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"password": "password"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def create_fixture(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict, dict, dict, dict, dict]:
    project = client.post("/api/projects", json={"name": "Lab", "description": "first"}, headers=headers).json()
    target = client.post(f"/api/projects/{project['id']}/targets", json={"base_url": "http://127.0.0.1:5000", "verification_path": "/me"}, headers=headers).json()
    identity = client.post(
        f"/api/projects/{project['id']}/identities",
        json={"display_name": "Alice", "role": "reader", "principal_pointer": "/data/name", "expected_principal": "alice", "bearer_token": "token-a"},
        headers=headers,
    ).json()
    operation = client.post(
        f"/api/projects/{project['id']}/openapi",
        json={"document": {"openapi": "3.0.3", "paths": {"/books/{id}": {"parameters": [{"name": "id", "in": "path"}], "get": {"operationId": "readBook"}}}}},
        headers=headers,
    ).json()[0]
    resource_type = client.post(
        f"/api/projects/{project['id']}/resource-types",
        json={"name": "book", "resource_id_pointer": "/data/id", "restricted_pointers": ["/data/secret"]},
        headers=headers,
    ).json()
    resource = client.post(
        f"/api/resource-types/{resource_type['id']}/resources",
        json={"external_id": "book-1", "owner_identity_id": identity["id"], "path_parameter": "id"},
        headers=headers,
    ).json()
    return project, target, identity, operation, resource_type, resource


def test_update_configuration_is_csrf_protected_and_secret_is_write_only(tmp_path) -> None:
    app = create_app(settings_for(tmp_path))
    with TestClient(app) as client:
        headers = login_headers(client)
        project, target, identity, operation, resource_type, resource = create_fixture(client, headers)

        assert client.patch(f"/api/projects/{project['id']}", json={"name": "Renamed", "description": "next"}).status_code == 403
        changed_project = client.patch(f"/api/projects/{project['id']}", json={"name": "Renamed", "description": "next"}, headers=headers)
        assert changed_project.status_code == 200
        assert changed_project.json() == {"id": project["id"], "name": "Renamed", "description": "next"}

        changed_target = client.patch(f"/api/targets/{target['id']}", json={"base_url": "http://127.0.0.1:5000/api", "verification_path": "/me", "timeout_seconds": 3, "request_limit": 20}, headers=headers)
        assert changed_target.status_code == 200
        assert changed_target.json()["timeout_seconds"] == 3
        assert client.patch(f"/api/targets/{target['id']}", json={"base_url": "http://localhost:5000", "verification_path": "/me", "timeout_seconds": 3, "request_limit": 20}, headers=headers).status_code == 422

        unchanged_secret = client.patch(
            f"/api/identities/{identity['id']}",
            json={"display_name": "Alice changed", "role": "reader", "principal_pointer": "/data/name", "expected_principal": "alice"},
            headers=headers,
        )
        assert unchanged_secret.status_code == 200
        assert "token-a" not in unchanged_secret.text
        session_factory = app.state.session_factory
        with session_factory() as session:
            original_ciphertext = session.get(IdentitySecret, identity["id"]).ciphertext

        replaced_secret = client.patch(
            f"/api/identities/{identity['id']}",
            json={"display_name": "Alice changed", "role": "reader", "principal_pointer": "/data/name", "expected_principal": "alice", "bearer_token": "token-b"},
            headers=headers,
        )
        assert replaced_secret.status_code == 200
        assert "token-b" not in replaced_secret.text
        with session_factory() as session:
            assert session.get(IdentitySecret, identity["id"]).ciphertext != original_ciphertext

        assert client.patch(f"/api/operations/{operation['id']}", json={"selected": False}, headers=headers).json()["selected"] is False
        changed_type = client.patch(f"/api/resource-types/{resource_type['id']}", json={"name": "volume", "resource_id_pointer": "/data/id", "restricted_pointers": ["/data/private"]}, headers=headers)
        assert changed_type.status_code == 200
        changed_resource = client.patch(f"/api/resources/{resource['id']}", json={"external_id": "book-2", "owner_identity_id": identity["id"], "path_parameter": "id"}, headers=headers)
        assert changed_resource.status_code == 200


def test_update_routes_reject_cross_project_records(tmp_path) -> None:
    app = create_app(settings_for(tmp_path))
    with TestClient(app) as client:
        headers = login_headers(client)
        first = create_fixture(client, headers)
        second_project = client.post("/api/projects", json={"name": "Second", "description": ""}, headers=headers).json()
        second_identity = client.post(
            f"/api/projects/{second_project['id']}/identities",
            json={"display_name": "Other", "role": "reader", "principal_pointer": "/data/name", "expected_principal": "other", "bearer_token": "token-other"},
            headers=headers,
        ).json()
        cross_owner = client.patch(
            f"/api/resources/{first[5]['id']}",
            json={"external_id": "book-1", "owner_identity_id": second_identity["id"], "path_parameter": "id"},
            headers=headers,
        )
        assert cross_owner.status_code == 422


def test_policy_update_versions_only_semantic_changes_and_keeps_run_snapshot(tmp_path) -> None:
    app = create_app(settings_for(tmp_path))
    with TestClient(app) as client:
        headers = login_headers(client)
        project, target, identity, operation, resource_type, resource = create_fixture(client, headers)
        policy = client.post(
            f"/api/projects/{project['id']}/policies",
            json={"operation_id": operation["id"], "resource_type_id": resource_type["id"], "decision": "ALLOW", "identity_id": identity["id"], "role": None, "resource_id": None},
            headers=headers,
        ).json()
        same = client.patch(f"/api/policies/{policy['id']}", json={"operation_id": operation["id"], "resource_type_id": resource_type["id"], "decision": "ALLOW", "identity_id": identity["id"], "role": None, "resource_id": None}, headers=headers)
        assert same.status_code == 200
        assert same.json()["version"] == 1
        updated = client.patch(f"/api/policies/{policy['id']}", json={"operation_id": operation["id"], "resource_type_id": resource_type["id"], "decision": "DENY", "identity_id": identity["id"], "role": None, "resource_id": None}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert client.get(f"/api/projects/{project['id']}/policies").json()[0]["version"] == 2

        session_factory = app.state.session_factory
        with session_factory.begin() as session:
            run = Run(project_id=project["id"], snapshot={"policy_version": 1, "target": {"base_url": target["base_url"]}})
            session.add(run)
        client.patch(f"/api/targets/{target['id']}", json={"base_url": "http://127.0.0.1:5000/changed", "verification_path": "/me", "timeout_seconds": 2, "request_limit": 10}, headers=headers)
        with session_factory() as session:
            persisted_run = session.query(Run).one()
            assert persisted_run.snapshot == {"policy_version": 1, "target": {"base_url": target["base_url"]}}
