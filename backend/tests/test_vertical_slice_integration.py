"""End-to-end API and worker coverage against a deterministic local lab."""

from __future__ import annotations

import ipaddress
import json
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Iterator

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.main import create_app


class LabHandler(BaseHTTPRequestHandler):
    """Read-only lab with two identities and a deliberate cross-user disclosure."""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler hook
        token = self.headers.get("Authorization")
        principal_by_token = {"Bearer alice-token": "alice", "Bearer bob-token": "bob"}
        principal = principal_by_token.get(token)
        if self.path == "/me" and principal is not None:
            self._send(200, {"data": {"username": principal}})
            return
        if self.path == "/books/book-1" and principal == "alice":
            self._send(200, {"data": {"id": "book-1", "secret": "owner-secret"}})
            return
        if self.path == "/books/book-1" and principal == "bob":
            self._send(403, {"data": {"id": "book-1", "secret": "owner-secret"}})
            return
        self._send(401, {"error": "unauthenticated"})

    def _send(self, status_code: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - inherited API
        return


@contextmanager
def local_lab() -> Iterator[ThreadingHTTPServer]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), LabHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def login_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"password": "password"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def wait_for_terminal_run(client: TestClient, project_id: int, run_id: int) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        runs = client.get(f"/api/projects/{project_id}/runs").json()
        run = next(item for item in runs if item["id"] == run_id)
        if run["status"] in {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"}:
            return run
        time.sleep(0.02)
    raise AssertionError("Worker did not finish the queued run.")


def test_full_read_only_vertical_slice_survives_browser_reload(tmp_path) -> None:
    with local_lab() as lab:
        settings = Settings(
            database_path=tmp_path / "app.sqlite3",
            admin_password="password",
            session_secret="s" * 32,
            secret_encryption_key=Fernet.generate_key().decode("ascii"),
            target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
            allowed_ports=frozenset({lab.server_port}),
            max_response_bytes=32768,
            default_timeout_seconds=5.0,
        )
        with TestClient(create_app(settings)) as client:
            csrf = login_headers(client)
            project = client.post("/api/projects", json={"name": "Live slice", "description": ""}, headers=csrf).json()
            project_id = project["id"]
            target = client.post(
                f"/api/projects/{project_id}/targets",
                json={"base_url": f"http://127.0.0.1:{lab.server_port}", "verification_path": "/me", "timeout_seconds": 1, "request_limit": 10},
                headers=csrf,
            ).json()
            alice = client.post(
                f"/api/projects/{project_id}/identities",
                json={"display_name": "Alice", "role": "reader", "principal_pointer": "/data/username", "expected_principal": "alice", "bearer_token": "alice-token"},
                headers=csrf,
            ).json()
            bob = client.post(
                f"/api/projects/{project_id}/identities",
                json={"display_name": "Bob", "role": "reader", "principal_pointer": "/data/username", "expected_principal": "bob", "bearer_token": "bob-token"},
                headers=csrf,
            ).json()
            document = {"openapi": "3.0.3", "paths": {"/books/{id}": {"parameters": [{"name": "id", "in": "path"}], "get": {"operationId": "readBook"}}}}
            operation = client.post(f"/api/projects/{project_id}/openapi", json={"document": document}, headers=csrf).json()[0]
            resource_type = client.post(
                f"/api/projects/{project_id}/resource-types",
                json={"name": "book", "resource_id_pointer": "/data/id", "restricted_pointers": ["/data/secret"]},
                headers=csrf,
            ).json()
            resource = client.post(
                f"/api/resource-types/{resource_type['id']}/resources",
                json={"external_id": "book-1", "owner_identity_id": alice["id"], "path_parameter": "id"},
                headers=csrf,
            ).json()
            second_resource = client.post(
                f"/api/resource-types/{resource_type['id']}/resources",
                json={"external_id": "book-2", "owner_identity_id": bob["id"], "path_parameter": "id"},
                headers=csrf,
            )
            assert second_resource.status_code == 201
            for identity_id, decision in ((alice["id"], "ALLOW"), (bob["id"], "DENY")):
                created = client.post(
                    f"/api/projects/{project_id}/policies",
                    json={"operation_id": operation["id"], "resource_type_id": resource_type["id"], "identity_id": identity_id, "role": None, "resource_id": None, "decision": decision},
                    headers=csrf,
                )
                assert created.status_code == 201

            matrix = client.get(f"/api/projects/{project_id}/matrix", params={"operation_id": operation["id"], "resource_id": resource["id"]})
            assert matrix.status_code == 200
            assert {case["actor_identity_id"] for case in matrix.json()} == {alice["id"], bob["id"]}

            created_run = client.post(
                f"/api/projects/{project_id}/runs",
                json={"target_id": target["id"], "operation_id": operation["id"], "resource_id": resource["id"]},
                headers=csrf,
            )
            assert created_run.status_code == 201
            finished = wait_for_terminal_run(client, project_id, created_run.json()["id"])
            assert finished["status"] == "COMPLETED"

            results = client.get(f"/api/runs/{created_run.json()['id']}/results")
            findings = client.get(f"/api/projects/{project_id}/findings")
            identities = client.get(f"/api/projects/{project_id}/identities")

        assert results.status_code == 200
        assert {result["execution_status"] for result in results.json()} == {"COMPLETED_RESPONSE"}
        assert {result["authorization_conclusion"] for result in results.json()} == {"POLICY_CONSISTENT_CASE", "CONFIRMED_VIOLATION"}
        assert findings.json()[0]["reproduction_count"] == 1
        assert findings.json()[0]["operation"] == {"method": "GET", "path": "/books/{id}"}
        assert all("bearer_token" not in identity for identity in identities.json())

        with TestClient(create_app(settings)) as reloaded_client:
            login_headers(reloaded_client)
            assert reloaded_client.get("/api/projects").json()[0]["name"] == "Live slice"
            assert len(reloaded_client.get(f"/api/projects/{project_id}/runs").json()) == 1
            assert reloaded_client.get(f"/api/projects/{project_id}/findings").json()[0]["reproduction_count"] == 1
