import ipaddress

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app


def headers(client: TestClient) -> dict[str, str]:
    login = client.post("/api/auth/login", json={"password": "password"})
    assert login.status_code == 200
    return {"X-CSRF-Token": login.json()["csrf_token"]}


def test_workflow_configuration_survives_api_reload(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "app.sqlite3",
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key=Fernet.generate_key().decode("ascii"),
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32768,
        default_timeout_seconds=5.0,
    )
    with TestClient(create_app(settings)) as client:
        csrf = headers(client)
        project = client.post("/api/projects", json={"name": "Slice", "description": ""}, headers=csrf).json()
        project_id = project["id"]
        target = client.post(f"/api/projects/{project_id}/targets", json={"base_url": "http://127.0.0.1:5000", "verification_path": "/me"}, headers=csrf)
        alice = client.post(f"/api/projects/{project_id}/identities", json={"display_name": "Alice", "role": "reader", "principal_pointer": "/data/name", "expected_principal": "alice", "bearer_token": "alice-token"}, headers=csrf)
        api_document = {"openapi": "3.0.3", "paths": {"/books/{id}": {"parameters": [{"name": "id", "in": "path"}], "get": {"operationId": "readBook"}}}}
        operations = client.post(f"/api/projects/{project_id}/openapi", json={"document": api_document}, headers=csrf)
        resource_type = client.post(f"/api/projects/{project_id}/resource-types", json={"name": "book", "resource_id_pointer": "/data/id", "restricted_pointers": ["/data/secret"]}, headers=csrf)
        resource = client.post(f"/api/resource-types/{resource_type.json()['id']}/resources", json={"external_id": "book-1", "owner_identity_id": alice.json()["id"], "path_parameter": "id"}, headers=csrf)

        targets = client.get(f"/api/projects/{project_id}/targets")
        types = client.get(f"/api/projects/{project_id}/resource-types")
        resources = client.get(f"/api/projects/{project_id}/resources")

    assert target.status_code == 201
    assert operations.status_code == 200
    assert resource.status_code == 201
    assert targets.json()[0]["base_url"] == "http://127.0.0.1:5000"
    assert types.json()[0]["restricted_pointers"] == ["/data/secret"]
    assert resources.json()[0]["external_id"] == "book-1"
