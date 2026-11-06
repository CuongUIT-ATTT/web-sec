#!/usr/bin/env python3
"""Configure a local authorization-testing web app for the approved BOLA lab.

This helper only calls the local web app's configuration API.  It reads bearer
credentials from the environment, keeps them in memory, and never creates a
run or calls a resource endpoint.  The optional health check is the only
network request made directly to the BOLA target.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar


DEFAULT_TARGET = "http://100.106.64.21:5003"
DEFAULT_PROJECT_NAME = "Controlled BOLA Lab (read-only)"
DEFAULT_OPERATION_PATH = "/books/{book_id}"
DEFAULT_RESOURCE_ID = "book-B1"
DEFAULT_WEB_URL = "http://127.0.0.1:8000"


class BootstrapError(RuntimeError):
    """A safe, secret-free bootstrap failure."""


class ApiClient(Protocol):
    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Send one request to the local web API and return JSON."""


@dataclass(frozen=True)
class BootstrapConfig:
    admin_password: str
    user_a_token: str
    user_b_token: str
    target_base_url: str
    openapi_path: Path
    web_base_url: str
    project_name: str
    operation_path: str
    resource_id: str
    replace_tokens: bool

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> "BootstrapConfig":
        required = (
            "AUTHZ_ADMIN_PASSWORD",
            "BOLA_USER_A_TOKEN",
            "BOLA_USER_B_TOKEN",
            "BOLA_TARGET_BASE_URL",
            "BOLA_OPENAPI_PATH",
        )
        missing = [name for name in required if not environ.get(name, "").strip()]
        if missing:
            raise BootstrapError("Missing required environment variables: " + ", ".join(missing))
        target = environ["BOLA_TARGET_BASE_URL"].strip().rstrip("/")
        if target != DEFAULT_TARGET:
            raise BootstrapError("BOLA_TARGET_BASE_URL must be the approved Controlled BOLA Lab URL.")
        openapi_path = Path(environ["BOLA_OPENAPI_PATH"]).expanduser()
        if not openapi_path.is_file():
            raise BootstrapError("BOLA_OPENAPI_PATH must name a readable reviewed OpenAPI JSON file.")
        return cls(
            admin_password=environ["AUTHZ_ADMIN_PASSWORD"],
            user_a_token=environ["BOLA_USER_A_TOKEN"],
            user_b_token=environ["BOLA_USER_B_TOKEN"],
            target_base_url=target,
            openapi_path=openapi_path,
            web_base_url=environ.get("BOLA_WEB_BASE_URL", DEFAULT_WEB_URL).rstrip("/"),
            project_name=environ.get("BOLA_PROJECT_NAME", DEFAULT_PROJECT_NAME).strip() or DEFAULT_PROJECT_NAME,
            operation_path=environ.get("BOLA_OPERATION_PATH", DEFAULT_OPERATION_PATH).strip() or DEFAULT_OPERATION_PATH,
            resource_id=environ.get("BOLA_RESOURCE_ID", DEFAULT_RESOURCE_ID).strip() or DEFAULT_RESOURCE_ID,
            replace_tokens=_environment_flag(environ.get("BOLA_REPLACE_TOKENS", "")),
        )


def _environment_flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


class LocalWebApi:
    """Minimal cookie and CSRF client for the loopback FastAPI service."""

    def __init__(self, base_url: str, admin_password: str) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"} or parsed.query or parsed.fragment:
            raise BootstrapError("BOLA_WEB_BASE_URL must be a loopback http URL without query or fragment.")
        self.base_url = base_url
        self._csrf_token = ""
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        login = self.request("POST", "/api/auth/login", {"password": admin_password}, include_csrf=False)
        csrf_token = login.get("csrf_token") if isinstance(login, dict) else None
        if not isinstance(csrf_token, str) or not csrf_token:
            raise BootstrapError("Local web login did not return a usable CSRF token.")
        self._csrf_token = csrf_token

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        include_csrf: bool = True,
    ) -> Any:
        if not path.startswith("/api/"):
            raise BootstrapError("Bootstrap only permits requests to the local /api/ surface.")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if include_csrf and method not in {"GET", "HEAD", "OPTIONS"}:
            headers["X-CSRF-Token"] = self._csrf_token
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=10) as response:
                raw = response.read()
        except HTTPError as error:
            raise BootstrapError(f"Local web API {method} {path} returned HTTP {error.code}.") from error
        except URLError as error:
            raise BootstrapError(f"Could not reach local web API at {self.base_url}.") from error
        try:
            return json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise BootstrapError(f"Local web API {method} {path} returned invalid JSON.") from error


def _one(items: list[dict[str, Any]], description: str) -> dict[str, Any] | None:
    if len(items) > 1:
        raise BootstrapError(f"Refusing to reconcile multiple {description} records; resolve duplicates in the UI first.")
    return items[0] if items else None


def _entity_id(entity: dict[str, Any], description: str) -> int:
    value = entity.get("id")
    if not isinstance(value, int):
        raise BootstrapError(f"Local web API returned an invalid {description} identifier.")
    return value


def _read_openapi(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BootstrapError("BOLA_OPENAPI_PATH must contain valid UTF-8 OpenAPI JSON.") from error
    if not isinstance(document, dict):
        raise BootstrapError("BOLA_OPENAPI_PATH must contain an OpenAPI JSON object.")
    return document


def _reconcile_target(client: ApiClient, project_id: int, config: BootstrapConfig) -> dict[str, Any]:
    desired = {
        "base_url": config.target_base_url,
        "verification_path": "/me",
        "timeout_seconds": 5.0,
        "request_limit": 100,
    }
    existing = _one(
        [target for target in client.request("GET", f"/api/projects/{project_id}/targets") if target.get("base_url") == config.target_base_url],
        "target",
    )
    if existing is None:
        return client.request("POST", f"/api/projects/{project_id}/targets", desired)
    return client.request("PATCH", f"/api/targets/{_entity_id(existing, 'target')}", desired)


def _reconcile_identity(
    client: ApiClient,
    project_id: int,
    *,
    display_name: str,
    expected_principal: str,
    token: str,
    replace_tokens: bool,
) -> dict[str, Any]:
    desired = {
        "display_name": display_name,
        "role": "user",
        "principal_pointer": "/principal/username",
        "expected_principal": expected_principal,
    }
    existing = _one(
        [identity for identity in client.request("GET", f"/api/projects/{project_id}/identities") if identity.get("display_name") == display_name],
        f"identity named {display_name}",
    )
    if existing is None:
        return client.request("POST", f"/api/projects/{project_id}/identities", {**desired, "bearer_token": token})
    if not existing.get("has_secret") and not replace_tokens:
        raise BootstrapError(f"Identity {display_name} has no usable stored credential; set BOLA_REPLACE_TOKENS=true to repair it.")
    if replace_tokens:
        desired["bearer_token"] = token
    return client.request("PATCH", f"/api/identities/{_entity_id(existing, 'identity')}", desired)


def _reconcile_resource_type(client: ApiClient, project_id: int) -> dict[str, Any]:
    desired = {"name": "book", "resource_id_pointer": "/data/id", "restricted_pointers": ["/data/secret"]}
    existing = _one(
        [item for item in client.request("GET", f"/api/projects/{project_id}/resource-types") if item.get("name") == "book"],
        "resource type named book",
    )
    if existing is None:
        return client.request("POST", f"/api/projects/{project_id}/resource-types", desired)
    return client.request("PATCH", f"/api/resource-types/{_entity_id(existing, 'resource type')}", desired)


def _reconcile_resource(client: ApiClient, project_id: int, resource_type: dict[str, Any], owner: dict[str, Any], config: BootstrapConfig) -> dict[str, Any]:
    desired = {"external_id": config.resource_id, "owner_identity_id": _entity_id(owner, "identity"), "path_parameter": "book_id"}
    resource_type_id = _entity_id(resource_type, "resource type")
    existing = _one(
        [item for item in client.request("GET", f"/api/projects/{project_id}/resources") if item.get("resource_type_id") == resource_type_id and item.get("external_id") == config.resource_id],
        f"resource {config.resource_id}",
    )
    if existing is None:
        return client.request("POST", f"/api/resource-types/{resource_type_id}/resources", desired)
    return client.request("PATCH", f"/api/resources/{_entity_id(existing, 'resource')}", desired)


def _reconcile_mapping(
    client: ApiClient,
    project_id: int,
    operation: dict[str, Any],
    resource_type: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile exactly one reviewed GET operation-to-book mapping."""
    operation_id = _entity_id(operation, "operation")
    resource_type_id = _entity_id(resource_type, "resource type")
    candidates = [
        item for item in client.request("GET", f"/api/projects/{project_id}/operation-resource-mappings")
        if item.get("operation_id") == operation_id and item.get("resource_type_id") == resource_type_id
    ]
    existing = _one(candidates, "mapping for the reviewed GET operation and book type")
    if existing is None:
        return client.request(
            "POST",
            f"/api/projects/{project_id}/operation-resource-mappings",
            {"operation_id": operation_id, "resource_type_id": resource_type_id, "selected": True},
        )
    if not existing.get("selected"):
        return client.request("PATCH", f"/api/operation-resource-mappings/{_entity_id(existing, 'mapping')}", {"selected": True})
    return existing


def _reconcile_policy(
    client: ApiClient,
    project_id: int,
    operation: dict[str, Any],
    resource_type: dict[str, Any],
    identity: dict[str, Any],
    decision: str,
) -> None:
    desired = {
        "operation_id": _entity_id(operation, "operation"),
        "resource_type_id": _entity_id(resource_type, "resource type"),
        "decision": decision,
        "identity_id": _entity_id(identity, "identity"),
        "role": None,
        "resource_id": None,
    }
    existing = _one(
        [
            item
            for item in client.request("GET", f"/api/projects/{project_id}/policies")
            if item.get("operation_id") == desired["operation_id"]
            and item.get("resource_type_id") == desired["resource_type_id"]
            and item.get("identity_id") == desired["identity_id"]
            and item.get("role") is None
            and item.get("resource_id") is None
        ],
        f"policy for identity {identity.get('display_name', 'unknown')}",
    )
    if existing is None:
        client.request("POST", f"/api/projects/{project_id}/policies", desired)
    else:
        client.request("PATCH", f"/api/policies/{_entity_id(existing, 'policy')}", desired)


def bootstrap(client: ApiClient, config: BootstrapConfig) -> dict[str, int]:
    """Reconcile reviewed configuration only; never create a run or target request."""
    projects = client.request("GET", "/api/projects")
    project = _one([item for item in projects if item.get("name") == config.project_name], f"project named {config.project_name}")
    if project is None:
        project = client.request(
            "POST",
            "/api/projects",
            {"name": config.project_name, "description": "Approved Controlled BOLA Lab configuration; GET/read-only observation."},
        )
    project_id = _entity_id(project, "project")
    target = _reconcile_target(client, project_id, config)
    user_a = _reconcile_identity(client, project_id, display_name="userA", expected_principal="userA", token=config.user_a_token, replace_tokens=config.replace_tokens)
    user_b = _reconcile_identity(client, project_id, display_name="userB", expected_principal="userB", token=config.user_b_token, replace_tokens=config.replace_tokens)
    client.request("POST", f"/api/projects/{project_id}/openapi", {"document": _read_openapi(config.openapi_path)})
    operations = client.request("GET", f"/api/projects/{project_id}/operations")
    operation = _one(
        [item for item in operations if item.get("method") == "GET" and item.get("path") == config.operation_path],
        f"GET operation {config.operation_path}",
    )
    if operation is None:
        raise BootstrapError("Reviewed OpenAPI JSON does not define the configured GET operation path.")
    if not operation.get("selected"):
        operation = client.request("PATCH", f"/api/operations/{_entity_id(operation, 'operation')}", {"selected": True})
    resource_type = _reconcile_resource_type(client, project_id)
    resource = _reconcile_resource(client, project_id, resource_type, user_b, config)
    mapping = _reconcile_mapping(client, project_id, operation, resource_type)
    _reconcile_policy(client, project_id, operation, resource_type, user_b, "ALLOW")
    _reconcile_policy(client, project_id, operation, resource_type, user_a, "DENY")
    return {
        "project_id": project_id,
        "target_id": _entity_id(target, "target"),
        "user_a_id": _entity_id(user_a, "identity"),
        "user_b_id": _entity_id(user_b, "identity"),
        "resource_id": _entity_id(resource, "resource"),
        "mapping_id": _entity_id(mapping, "mapping"),
    }


def health_smoke(config: BootstrapConfig) -> int:
    """GET only the approved target health endpoint and expose no response body."""
    request = Request(f"{config.target_base_url}/health", headers={"Accept": "application/json"}, method="GET")
    try:
        with build_opener().open(request, timeout=5) as response:
            response.read(0)
            return response.status
    except HTTPError as error:
        error.read(0)
        return error.code
    except URLError as error:
        raise BootstrapError("Could not reach the Controlled BOLA Lab health endpoint.") from error


def verify_identities(client: ApiClient, target_id: int, identity_ids: tuple[int, int]) -> list[bool]:
    """Use the web API's existing /me verifier and return only safe booleans."""
    confirmed: list[bool] = []
    for identity_id in identity_ids:
        result = client.request("POST", f"/api/identities/{identity_id}/verify?target_id={target_id}")
        confirmed.append(bool(result.get("principal_confirmed")))
    return confirmed


def main(argv: list[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure the authorized Controlled BOLA Lab in a local web app without creating a run.")
    parser.add_argument("--health-smoke", action="store_true", help="GET only the target /health endpoint and print its status code.")
    parser.add_argument("--verify-identities", action="store_true", help="Use the local web app to perform redacted /me verification for userA and userB.")
    args = parser.parse_args(argv)
    try:
        config = BootstrapConfig.from_environment(os.environ if environ is None else environ)
        client = LocalWebApi(config.web_base_url, config.admin_password)
        result = bootstrap(client, config)
        print(f"Configured project_id={result['project_id']} target_id={result['target_id']} resource_id={result['resource_id']}; no run was created.")
        if args.health_smoke:
            print(f"Health smoke: HTTP {health_smoke(config)}")
        if args.verify_identities:
            confirmed = verify_identities(client, result["target_id"], (result["user_a_id"], result["user_b_id"]))
            print(f"Identity verification: userA={'pass' if confirmed[0] else 'fail'}, userB={'pass' if confirmed[1] else 'fail'}")
        return 0
    except BootstrapError as error:
        print(f"Bootstrap failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
