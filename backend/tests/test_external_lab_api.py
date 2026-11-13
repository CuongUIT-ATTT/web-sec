import ipaddress
import time

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app.core.settings import Settings
from backend.app.external_lab.contracts import BRIDGE_EVENT_AUDIENCE, canonical_signature
from backend.app.external_lab.service import claim_next_job
from backend.app.main import create_app


def bridge_settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "app.sqlite3",
        admin_password="password",
        session_secret="s" * 32,
        secret_encryption_key=Fernet.generate_key().decode("ascii"),
        target_networks=(ipaddress.ip_network("127.0.0.1/32"),),
        allowed_ports=frozenset({5000}),
        max_response_bytes=32768,
        default_timeout_seconds=5.0,
        external_lab_bridge_enabled=True,
        external_lab_bridge_socket_path=tmp_path / "missing.sock",
        external_lab_bridge_shared_secret="b" * 32,
    )


def csrf(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"password": "password"})
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def event_headers(
    secret: str,
    path: str,
    body: bytes,
    nonce: str = "unique-nonce",
) -> dict[str, str]:
    timestamp = str(int(time.time()))
    return {
        "X-Bridge-Timestamp": timestamp,
        "X-Bridge-Nonce": nonce,
        "X-Bridge-Audience": BRIDGE_EVENT_AUDIENCE,
        "X-Bridge-Signature": canonical_signature(
            secret,
            method="POST",
            path=path,
            body=body,
            timestamp=timestamp,
            nonce=nonce,
            audience=BRIDGE_EVENT_AUDIENCE,
        ),
        "Content-Type": "application/json",
    }


def test_external_job_requires_csrf_and_accepts_only_bridge_events(tmp_path) -> None:
    settings = bridge_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        headers = csrf(client)
        project = client.post(
            "/api/projects",
            json={"name": "External", "description": ""},
            headers=headers,
        )
        project_id = project.json()["id"]
        path = f"/api/projects/{project_id}/external-lab-jobs/read-only-verification"
        assert client.post(path).status_code == 403
        created = client.post(path, headers=headers)
        assert created.status_code == 201
        public_id = created.json()["public_id"]
        assert client.post(path, headers=headers).status_code == 409

        with app.state.session_factory.begin() as session:
            assert claim_next_job(session) is not None

        callback_path = f"/api/internal/bridge/jobs/{public_id}/events"
        payload = (
            b'{"sequence":1,"status":"RUNNING",'
            b'"summary":{"target_label":"LOCAL_VAMPI_READ_ONLY"}}'
        )
        assert client.post(callback_path, content=payload).status_code == 401
        accepted = client.post(
            callback_path,
            content=payload,
            headers=event_headers(
                settings.external_lab_bridge_shared_secret,
                callback_path,
                payload,
            ),
        )
        assert accepted.status_code == 204
        replay = client.post(
            callback_path,
            content=payload,
            headers=event_headers(
                settings.external_lab_bridge_shared_secret,
                callback_path,
                payload,
            ),
        )
        assert replay.status_code == 409
        listed = client.get(f"/api/projects/{project_id}/external-lab-jobs")
        assert listed.status_code == 200
        assert listed.json()[0]["status"] == "RUNNING"
        assert "target_label" in listed.json()[0]["result_summary"]
        assert "command" not in listed.json()[0]


def test_external_job_rejects_invalid_hmac_and_state_transition(tmp_path) -> None:
    settings = bridge_settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = csrf(client)
        project_id = client.post(
            "/api/projects",
            json={"name": "External", "description": ""},
            headers=headers,
        ).json()["id"]
        created = client.post(
            f"/api/projects/{project_id}/external-lab-jobs/read-only-verification",
            headers=headers,
        ).json()
        callback_path = f"/api/internal/bridge/jobs/{created['public_id']}/events"
        invalid_summary = b'{"sequence":1,"status":"RUNNING","summary":{"command":"no"}}'
        signed = event_headers(
            settings.external_lab_bridge_shared_secret,
            callback_path,
            invalid_summary,
        )
        assert client.post(callback_path, content=invalid_summary, headers=signed).status_code == 422
        valid = b'{"sequence":1,"status":"RUNNING","summary":{}}'
        assert client.post(
            callback_path,
            content=valid,
            headers=event_headers(
                settings.external_lab_bridge_shared_secret,
                callback_path,
                valid,
                nonce="different-nonce",
            ),
        ).status_code == 409
