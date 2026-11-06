"""Tests for the secret-safe Controlled BOLA Lab bootstrap helper."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "tools" / "bootstrap_controlled_bola_lab.py"
SPEC = importlib.util.spec_from_file_location("controlled_bola_bootstrap", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
bootstrap_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap_module
SPEC.loader.exec_module(bootstrap_module)


class FakeConfigurationApi:
    """Stateful local configuration API double; it never receives target traffic."""

    def __init__(self) -> None:
        self.projects: list[dict[str, Any]] = []
        self.targets: list[dict[str, Any]] = []
        self.identities: list[dict[str, Any]] = []
        self.operations: list[dict[str, Any]] = []
        self.resource_types: list[dict[str, Any]] = []
        self.resources: list[dict[str, Any]] = []
        self.policies: list[dict[str, Any]] = []
        self.mappings: list[dict[str, Any]] = []
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self._next_id = 1

    def _new(self, collection: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
        item = {"id": self._next_id, **payload}
        self._next_id += 1
        collection.append(item)
        return item

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        self.calls.append((method, path, payload))
        if method == "GET" and path == "/api/projects":
            return self.projects
        if method == "POST" and path == "/api/projects":
            return self._new(self.projects, payload or {})
        if method == "GET" and path.endswith("/targets"):
            return self.targets
        if method == "POST" and path.endswith("/targets"):
            return self._new(self.targets, {"project_id": int(path.split("/")[3]), **(payload or {})})
        if method == "PATCH" and path.startswith("/api/targets/"):
            item = self._by_id(self.targets, path)
            item.update(payload or {})
            return item
        if method == "GET" and path.endswith("/identities"):
            return self.identities
        if method == "POST" and path.endswith("/identities"):
            item = self._new(self.identities, {"project_id": int(path.split("/")[3]), **(payload or {})})
            item.pop("bearer_token")
            item["has_secret"] = True
            return item
        if method == "PATCH" and path.startswith("/api/identities/"):
            item = self._by_id(self.identities, path)
            item.update(payload or {})
            item.pop("bearer_token", None)
            return item
        if method == "POST" and path.endswith("/openapi"):
            document = (payload or {})["document"]
            for path_key, path_item in document["paths"].items():
                if "get" in path_item and not any(item["path"] == path_key for item in self.operations):
                    self._new(self.operations, {"project_id": int(path.split("/")[3]), "operation_key": path_item["get"].get("operationId", f"GET:{path_key}"), "method": "GET", "path": path_key, "selected": True})
            return self.operations
        if method == "GET" and path.endswith("/operations"):
            return self.operations
        if method == "PATCH" and path.startswith("/api/operations/"):
            item = self._by_id(self.operations, path)
            item.update(payload or {})
            return item
        if method == "GET" and path.endswith("/resource-types"):
            return self.resource_types
        if method == "POST" and path.endswith("/resource-types"):
            return self._new(self.resource_types, {"project_id": int(path.split("/")[3]), **(payload or {})})
        if method == "PATCH" and path.startswith("/api/resource-types/"):
            item = self._by_id(self.resource_types, path)
            item.update(payload or {})
            return item
        if method == "GET" and path.endswith("/resources"):
            return self.resources
        if method == "POST" and "/resource-types/" in path and path.endswith("/resources"):
            return self._new(self.resources, {"resource_type_id": int(path.split("/")[3]), **(payload or {})})
        if method == "PATCH" and path.startswith("/api/resources/"):
            item = self._by_id(self.resources, path)
            item.update(payload or {})
            return item
        if method == "GET" and path.endswith("/operation-resource-mappings"):
            return self.mappings
        if method == "POST" and path.endswith("/operation-resource-mappings"):
            return self._new(self.mappings, {"project_id": int(path.split("/")[3]), **(payload or {})})
        if method == "PATCH" and path.startswith("/api/operation-resource-mappings/"):
            item = self._by_id(self.mappings, path)
            item.update(payload or {})
            return item
        if method == "GET" and path.endswith("/policies"):
            return self.policies
        if method == "POST" and path.endswith("/policies"):
            return self._new(self.policies, payload or {})
        if method == "PATCH" and path.startswith("/api/policies/"):
            item = self._by_id(self.policies, path)
            item.update(payload or {})
            return item
        raise AssertionError(f"Unexpected request: {method} {path}")

    @staticmethod
    def _by_id(collection: list[dict[str, Any]], path: str) -> dict[str, Any]:
        identifier = int(path.rsplit("/", 1)[1].split("?", 1)[0])
        return next(item for item in collection if item["id"] == identifier)


@pytest.fixture
def reviewed_openapi(tmp_path: Path) -> Path:
    path = tmp_path / "bola.openapi.json"
    path.write_text(
        json.dumps({"openapi": "3.0.3", "paths": {"/books/{book_id}": {"parameters": [{"name": "book_id", "in": "path"}], "get": {"operationId": "getBook"}}}}),
        encoding="utf-8",
    )
    return path


def configuration(reviewed_openapi: Path) -> Any:
    return bootstrap_module.BootstrapConfig(
        admin_password="admin-secret",
        user_a_token="user-a-token-secret",
        user_b_token="user-b-token-secret",
        target_base_url=bootstrap_module.DEFAULT_TARGET,
        openapi_path=reviewed_openapi,
        web_base_url="http://127.0.0.1:8000",
        project_name=bootstrap_module.DEFAULT_PROJECT_NAME,
        operation_path=bootstrap_module.DEFAULT_OPERATION_PATH,
        resource_id=bootstrap_module.DEFAULT_RESOURCE_ID,
        replace_tokens=False,
    )


def test_bootstrap_reconciles_without_duplicates_or_run(reviewed_openapi: Path) -> None:
    api = FakeConfigurationApi()
    config = configuration(reviewed_openapi)

    first = bootstrap_module.bootstrap(api, config)
    second = bootstrap_module.bootstrap(api, config)

    assert first == second
    assert len(api.projects) == len(api.targets) == len(api.resource_types) == len(api.resources) == 1
    assert len(api.identities) == len(api.policies) == 2
    assert len(api.operations) == len(api.mappings) == 1
    assert api.mappings[0]["selected"] is True
    assert api.resources[0]["owner_identity_id"] == next(item["id"] for item in api.identities if item["display_name"] == "userB")
    assert {item["decision"] for item in api.policies} == {"ALLOW", "DENY"}
    assert all("/runs" not in path for _, path, _ in api.calls)
    assert all("/batch-runs" not in path for _, path, _ in api.calls)
    assert all("/connection-test" not in path for _, path, _ in api.calls)
    assert all("/verify" not in path for _, path, _ in api.calls)


def test_environment_validation_never_echoes_secret_values(reviewed_openapi: Path) -> None:
    environment = {
        "AUTHZ_ADMIN_PASSWORD": "admin-secret",
        "BOLA_USER_A_TOKEN": "user-a-token-secret",
        "BOLA_USER_B_TOKEN": "user-b-token-secret",
        "BOLA_TARGET_BASE_URL": bootstrap_module.DEFAULT_TARGET,
        "BOLA_OPENAPI_PATH": str(reviewed_openapi),
    }
    config = bootstrap_module.BootstrapConfig.from_environment(environment)
    assert config.replace_tokens is False

    with pytest.raises(bootstrap_module.BootstrapError) as error:
        bootstrap_module.BootstrapConfig.from_environment({**environment, "BOLA_USER_A_TOKEN": ""})

    message = str(error.value)
    assert "BOLA_USER_A_TOKEN" in message
    assert "user-a-token-secret" not in message
    assert "admin-secret" not in message


def test_health_smoke_uses_only_get_health(monkeypatch: pytest.MonkeyPatch, reviewed_openapi: Path) -> None:
    requested: list[object] = []

    class Response:
        status = 200

        def read(self, amount: int = -1) -> bytes:
            assert amount == 0
            return b""

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    class Opener:
        def open(self, request: object, timeout: float) -> Response:
            requested.append((request, timeout))
            return Response()

    monkeypatch.setattr(bootstrap_module, "build_opener", lambda: Opener())

    assert bootstrap_module.health_smoke(configuration(reviewed_openapi)) == 200
    request, timeout = requested[0]
    assert request.get_method() == "GET"
    assert request.full_url == "http://100.106.64.21:5003/health"
    assert timeout == 5


def test_main_forwards_health_smoke_without_exposing_tokens(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], reviewed_openapi: Path) -> None:
    config = configuration(reviewed_openapi)
    monkeypatch.setattr(bootstrap_module.BootstrapConfig, "from_environment", classmethod(lambda cls, environ: config))
    monkeypatch.setattr(bootstrap_module, "LocalWebApi", lambda base_url, admin_password: object())
    monkeypatch.setattr(
        bootstrap_module,
        "bootstrap",
        lambda client, configured: {"project_id": 1, "target_id": 2, "resource_id": 3, "user_a_id": 4, "user_b_id": 5},
    )
    monkeypatch.setattr(bootstrap_module, "health_smoke", lambda configured: 204)

    assert bootstrap_module.main(["--health-smoke"], {}) == 0

    captured = capsys.readouterr()
    assert "Health smoke: HTTP 204" in captured.out
    assert config.admin_password not in captured.out + captured.err
    assert config.user_a_token not in captured.out + captured.err
    assert config.user_b_token not in captured.out + captured.err


def test_main_does_not_print_tokens_when_configuration_is_incomplete(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = bootstrap_module.main([], {"AUTHZ_ADMIN_PASSWORD": "admin-secret", "BOLA_USER_A_TOKEN": "user-a-token-secret"})

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "BOLA_USER_B_TOKEN" in captured.err
    assert "admin-secret" not in captured.err
    assert "user-a-token-secret" not in captured.err
    assert captured.out == ""
