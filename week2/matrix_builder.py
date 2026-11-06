"""Build fixture-backed, read-only authorization cases from endpoint inventory."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}


def filter_fixtures_for_roles(
    fixtures: list[dict[str, str]], roles: Iterable[str] | Mapping[str, Any]
) -> list[dict[str, str]]:
    """Keep only fixtures whose owner_role is present in the configured roles."""
    role_set = set(roles.keys()) if isinstance(roles, Mapping) else set(roles)
    return [fixture for fixture in fixtures if fixture.get("owner_role") in role_set]


def _is_admin_role(role: str, roles_config: Mapping[str, Any] | None = None) -> bool:
    if isinstance(roles_config, Mapping):
        entry = roles_config.get(role)
        if isinstance(entry, Mapping) and "is_admin" in entry:
            return bool(entry["is_admin"])
    return role.startswith("admin")


def load_ownership(path: str | Path) -> list[dict[str, str]]:
    """Load only known lab fixtures from the Week 1 ownership CSV."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    required = {"resource_type", "resource_id", "owner_role", "owner_username", "path_template"}
    if not rows or any(not required.issubset(row) for row in rows):
        raise ValueError("Ownership CSV is missing required fixture columns.")

    fixtures: list[dict[str, str]] = []
    for row in rows:
        if not all(row.get(field, "") for field in required):
            raise ValueError("Ownership CSV contains an incomplete fixture row.")
        fixtures.append({field: row[field] for field in required})
    return fixtures


def _case_id(operation_id: str, scenario: str, actor: str, resource_id: str) -> str:
    safe_operation = "".join(char if char.isalnum() else "-" for char in operation_id).strip("-")
    safe_resource = "".join(char if char.isalnum() else "-" for char in resource_id).strip("-")
    return f"{safe_operation}--{scenario}--{actor}--{safe_resource}"


def _render_path(template: str, endpoint: dict[str, Any], fixture: dict[str, str]) -> str:
    path = template
    for parameter in endpoint["path_params"]:
        if parameter not in {"book_title", "username"}:
            raise ValueError(f"Unsupported fixture parameter: {parameter}")
        path = path.replace("{" + parameter + "}", fixture["resource_id"])
    return path


def _matching_fixtures(endpoint: dict[str, Any], fixtures: list[dict[str, str]]) -> list[dict[str, str]]:
    return [fixture for fixture in fixtures if fixture["path_template"] == endpoint["path"]]


def _append_book_cases(
    cases: list[dict[str, Any]], endpoint: dict[str, Any], fixture: dict[str, str], roles: list[str]
) -> None:
    owner = fixture["owner_role"]
    path = _render_path(endpoint["path"], endpoint, fixture)
    common = {
        "risk_category": "BOLA",
        "operation_id": endpoint["operation_id"],
        "method": endpoint["method"],
        "endpoint": path,
        "fixture": fixture,
        "enabled_read_only": True,
    }
    cases.append(
        {
            **common,
            "case_id": _case_id(endpoint["operation_id"], "owner-control", owner, fixture["resource_id"]),
            "scenario": "owner_control",
            "actor_role": owner,
            "expected_outcome": "owner_success",
        }
    )
    for role in roles:
        if role == owner:
            continue
        cases.append(
            {
                **common,
                "case_id": _case_id(endpoint["operation_id"], "cross-user", role, fixture["resource_id"]),
                "scenario": "cross_user",
                "actor_role": role,
                "expected_outcome": "deny",
            }
        )
    for scenario in ("anonymous", "invalid_token"):
        cases.append(
            {
                **common,
                "case_id": _case_id(endpoint["operation_id"], scenario, scenario, fixture["resource_id"]),
                "scenario": scenario,
                "actor_role": None,
                "expected_outcome": "deny",
            }
        )


def _append_public_observation(
    cases: list[dict[str, Any]], endpoint: dict[str, Any], fixture: dict[str, str]
) -> None:
    cases.append(
        {
            "case_id": _case_id(endpoint["operation_id"], "anonymous-observation", "anonymous", fixture["resource_id"]),
            "risk_category": "PUBLIC_OBJECT_READ",
            "operation_id": endpoint["operation_id"],
            "method": endpoint["method"],
            "endpoint": _render_path(endpoint["path"], endpoint, fixture),
            "fixture": fixture,
            "enabled_read_only": True,
            "scenario": "anonymous_observation",
            "actor_role": None,
            "expected_outcome": "observe",
        }
    )


def _append_excessive_exposure_cases(
    cases: list[dict[str, Any]],
    endpoint: dict[str, Any],
    roles: list[str],
    roles_config: Mapping[str, Any] | None = None,
) -> None:
    resource_id = endpoint["path"].strip("/").replace("/", "-") or "root"
    synthetic_fixture = {
        "resource_type": "debug_endpoint",
        "resource_id": resource_id,
        "owner_role": "admin",
        "owner_username": "admin",
        "path_template": endpoint["path"],
    }
    common = {
        "risk_category": "EXCESSIVE_DATA_EXPOSURE",
        "operation_id": endpoint["operation_id"],
        "method": endpoint["method"],
        "endpoint": endpoint["path"],
        "fixture": synthetic_fixture,
        "enabled_read_only": True,
    }
    cases.append(
        {
            **common,
            "case_id": _case_id(endpoint["operation_id"], "anonymous", "anonymous", resource_id),
            "scenario": "anonymous",
            "actor_role": None,
            "expected_outcome": "deny",
        }
    )
    for role in roles:
        is_admin = _is_admin_role(role, roles_config)
        scenario = "admin_control" if is_admin else "unprivileged_role"
        cases.append(
            {
                **common,
                "case_id": _case_id(endpoint["operation_id"], scenario.replace("_", "-"), role, resource_id),
                "scenario": scenario,
                "actor_role": role,
                "expected_outcome": "observe" if is_admin else "deny",
            }
        )


def build_test_matrix(
    endpoints: list[dict[str, Any]],
    fixtures: list[dict[str, str]],
    roles: list[str],
    roles_config: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Generate tests only where an endpoint matches a known fixture path or read-only exposure candidate."""
    active_fixtures = filter_fixtures_for_roles(fixtures, roles)
    cases: list[dict[str, Any]] = []
    for endpoint in endpoints:
        if endpoint["forbidden"] or endpoint["method"] not in READ_ONLY_METHODS:
            continue
        if (
            endpoint.get("is_excessive_data_exposure_candidate")
            or (endpoint.get("is_bfla_candidate") and not endpoint.get("path_params"))
        ):
            _append_excessive_exposure_cases(cases, endpoint, roles, roles_config)
            continue
        for fixture in _matching_fixtures(endpoint, active_fixtures):
            if endpoint["requires_auth"] and endpoint["is_bola_candidate"]:
                _append_book_cases(cases, endpoint, fixture, roles)
            elif endpoint["public_object_read"]:
                _append_public_observation(cases, endpoint, fixture)
    return sorted(cases, key=lambda item: item["case_id"])
