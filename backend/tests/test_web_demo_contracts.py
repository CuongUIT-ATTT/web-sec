"""Read contracts against isolated SQLite; no app lifespan, worker or target traffic."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.api.routes import get_session
from backend.app.api.workflow_routes import router
from backend.app.core.auth import require_admin
from backend.app.persistence.database import Base, create_sqlite_engine
from backend.app.persistence.models import (
    Finding, FindingReproduction, Identity, OpenApiOperation, OperationResourceMapping, Policy, Project,
    Resource, ResourceType, Run, RunResult,
)


@pytest.fixture
def contract(tmp_path):
    engine = create_sqlite_engine(tmp_path / "contracts.sqlite3")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Project(id=1, name="one"), Project(id=2, name="two")])
        session.add_all([
            Identity(id=1, project_id=1, display_name="owner", role="admin"),
            Identity(id=2, project_id=1, display_name="actor", role="reader"),
            Identity(id=3, project_id=2, display_name="foreign", role="reader"),
            OpenApiOperation(id=1, project_id=1, operation_key="get", method="GET", path="/items/{id}", selected=True),
            OpenApiOperation(id=2, project_id=2, operation_key="get", method="GET", path="/items/{id}"),
            ResourceType(id=1, project_id=1, name="item", resource_id_pointer="/id", restricted_pointers=["/secret"]),
            ResourceType(id=2, project_id=2, name="item", resource_id_pointer="/id", restricted_pointers=["/secret"]),
        ])
        session.flush()
        session.add_all([
            Resource(id=1, resource_type_id=1, external_id="one", owner_identity_id=1, path_parameter="id"),
            Resource(id=2, resource_type_id=2, external_id="two", owner_identity_id=3, path_parameter="id"),
            OperationResourceMapping(id=1, project_id=1, operation_id=1, resource_type_id=1, selected=True),
        ])
        session.commit()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[require_admin] = lambda: None
        with TestClient(app) as client:
            yield client, session
    engine.dispose()


def matrix(client):
    response = client.get("/api/projects/1/matrix?operation_id=1&resource_id=1")
    assert response.status_code == 200
    return response.json()


def add_policy(session, identifier, decision, **scope):
    row = Policy(id=identifier, version=7, operation_id=1, resource_type_id=1, decision=decision, **scope)
    session.add(row)
    session.commit()
    return row


def test_no_match_preserves_keys_owner_and_no_admin_bypass(contract):
    client, _ = contract
    rows = matrix(client)
    assert [row["actor_identity_id"] for row in rows] == [1, 2]
    assert [row["control_type"] for row in rows] == ["OWNER_CONTROL", "CROSS_IDENTITY"]
    for row in rows:
        assert row["operation_id"] == 1
        assert row["owner_identity_id"] == 1
        assert row["case_key"] == f"operation:1:resource:1:actor:{row['actor_identity_id']}"
        assert row["policy_status"] == "NO_MATCH"
        assert (row["resolved_decision"], row["policy_id"], row["policy_version"]) == (None, None, None)
        assert "identity.unverified_precheck" in row["warnings"]
        assert "policy.no_resolved_rule" in row["warnings"]


def test_explicit_unknown_is_resolved_and_versioned(contract):
    client, session = contract
    add_policy(session, 1, "UNKNOWN", role="reader")
    actor = matrix(client)[1]
    assert actor["policy_status"] == "RESOLVED"
    assert (actor["resolved_decision"], actor["policy_id"], actor["policy_version"]) == ("UNKNOWN", 1, 7)


def test_conflicting_top_rules_have_no_selected_policy(contract):
    client, session = contract
    add_policy(session, 1, "ALLOW", role="reader")
    add_policy(session, 2, "DENY", role="reader")
    actor = matrix(client)[1]
    assert actor["policy_status"] == "UNRESOLVED_CONFLICT"
    assert (actor["resolved_decision"], actor["policy_id"], actor["policy_version"]) == (None, None, None)
    assert "policy.unresolved_conflict" in actor["warnings"]


def test_role_resource_then_identity_specificity_and_deterministic_tie(contract):
    client, session = contract
    add_policy(session, 1, "DENY", role="reader")
    add_policy(session, 2, "ALLOW", role="reader", resource_id=1)
    assert matrix(client)[1]["policy_id"] == 2
    add_policy(session, 3, "DENY", identity_id=2)
    assert matrix(client)[1]["policy_id"] == 3
    add_policy(session, 4, "ALLOW", identity_id=2, resource_id=1)
    add_policy(session, 5, "ALLOW", identity_id=2, resource_id=1)
    assert matrix(client)[1]["policy_id"] == 4
    add_policy(session, 6, "ALLOW", role="admin")
    assert matrix(client)[0]["resolved_decision"] == "ALLOW"


@pytest.mark.parametrize("operation,resource", [(2, 1), (1, 2), (999, 1), (1, 999)])
def test_matrix_rejects_foreign_or_missing_scope(contract, operation, resource):
    client, _ = contract
    assert client.get(f"/api/projects/1/matrix?operation_id={operation}&resource_id={resource}").status_code == 422


@pytest.mark.parametrize("scope_change", ["mapping_unselected", "mapping_missing", "operation_unselected", "write_method"])
def test_matrix_requires_explicit_selected_get_mapping(contract, scope_change):
    client, session = contract
    if scope_change == "mapping_unselected":
        session.get(OperationResourceMapping, 1).selected = False
    elif scope_change == "mapping_missing":
        session.delete(session.get(OperationResourceMapping, 1))
    elif scope_change == "operation_unselected":
        session.get(OpenApiOperation, 1).selected = False
    else:
        session.get(OpenApiOperation, 1).method = "POST"
    session.commit()
    assert client.get("/api/projects/1/matrix?operation_id=1&resource_id=1").status_code == 422


def test_reproductions_are_persisted_run_scoped_and_project_isolated(contract):
    client, session = contract
    session.add_all([Run(id=1, project_id=1), Run(id=2, project_id=1), Run(id=3, project_id=2)])
    for identifier, project in [(1, 1), (2, 1), (3, 2)]:
        session.add(Finding(id=identifier, project_id=project, fingerprint=str(identifier), conclusion="BOLA", operation_method="GET", operation_path="/items/{id}", policy_id=1, policy_version=7, resource_type_id=project, resource_pointer="/id"))
    for identifier, run, key in [(1, 1, "resource:1:actor:2"), (2, 2, None), (3, 3, "foreign")]:
        session.add(RunResult(id=identifier, run_id=run, case_key=key, execution_status="COMPLETED", authorization_conclusion="BOLA", response_metadata={"private": "do-not-expose"}))
    session.flush()
    for identifier, finding, result in [(1, 1, 1), (2, 1, 2), (3, 3, 3), (4, 1, 3)]:
        # Last link models malformed historical cross-project data: it must never leak.
        session.add(FindingReproduction(id=identifier, finding_id=finding, run_result_id=result, actor_identity_id=2, resource_id=1))
    session.commit()
    aggregate = client.get("/api/projects/1/findings").json()
    assert [row["id"] for row in aggregate] == [2, 1]
    assert aggregate[0]["reproductions"] == []
    assert aggregate[1]["reproduction_count"] == 2
    assert aggregate[1]["reproductions"][1]["case_key"] is None
    scoped = client.get("/api/projects/1/findings?run_id=1").json()
    assert len(scoped) == 1
    assert scoped[0]["reproduction_count"] == 1
    assert scoped[0]["reproductions"] == [{"run_id": 1, "run_result_id": 1, "case_key": "resource:1:actor:2", "actor_identity_id": 2, "resource_id": 1}]
    assert "do-not-expose" not in str(aggregate)
    assert client.get("/api/projects/1/findings?run_id=3").status_code == 404
    assert client.get("/api/projects/1/findings?run_id=999").status_code == 404
    assert client.get("/api/projects/999/findings").status_code == 404
    assert client.get("/api/projects/1/findings?run_id=2").json()[0]["reproductions"][0]["case_key"] is None


def evidence_payload():
    return {
        "schema_version": 1, "engine": "web-evaluator-v1",
        "run_id": 1, "case_key": "resource:1:actor:2",
        "resource_id": 1, "actor_identity_id": 2, "owner_identity_id": 1,
        "owner_control_valid": True, "owner_http_status": 200,
        "owner_execution_status": "COMPLETED_RESPONSE",
        "owner_body_truncated": False, "owner_json_parse_error": False,
        "owner_principal_matches": True, "actor_principal_matches": True,
        "owner_resource_matches": True, "actor_resource_matches": True,
        "owner_restricted_evidence_valid": True, "restricted_fields_match_owner": True,
        "policy_id": 1, "policy_version": 7, "policy_decision": "DENY",
        "policy_resolution": "RESOLVED",
    }


def store_result(session, metadata):
    session.add_all([Run(id=1, project_id=1), Run(id=2, project_id=2)])
    session.flush()
    session.add_all([
        RunResult(run_id=1, case_key="resource:1:actor:2", execution_status="COMPLETED_RESPONSE",
                  authorization_conclusion="CONFIRMED_VIOLATION", reason_codes=["evidence.test"],
                  http_status=403, response_metadata=metadata),
        RunResult(run_id=2, case_key="foreign-canary", execution_status="CANCELLED",
                  authorization_conclusion="NOT_EVALUATED", response_metadata={}),
    ])
    session.commit()


def test_result_evidence_typed_allowlist_and_project_isolation(contract):
    client, session = contract
    evidence = evidence_payload()
    evidence["raw_body"] = "secret-canary"
    store_result(session, {"body_length": 42, "body_truncated": False, "json_parse_error": False,
                           "evidence": evidence, "token": "secret-canary"})
    response = client.get("/api/runs/1/results")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["http_status"] == 403
    assert rows[0]["response_metadata"] == {
        "body_length": 42, "body_truncated": False, "json_parse_error": False,
        "evidence": evidence_payload(),
    }
    assert "canary" not in response.text
    assert client.get("/api/runs/999/results").status_code == 404
    schema = client.get("/openapi.json").json()
    assert "ResultEvidenceView" in schema["components"]["schemas"]


@pytest.mark.parametrize("change", [
    {"run_id": 2}, {"case_key": "foreign-canary"}, {"schema_version": 2},
    {"schema_version": True},
    {"engine": "unknown-canary"}, {"owner_control_valid": "true"},
    {"owner_http_status": "200"}, {"policy_decision": "unknown-canary"},
    {"owner_execution_status": "unknown-canary"}, {"resource_id": True},
    {"policy_resolution": None},
])
def test_invalid_or_mismatched_evidence_is_unavailable(contract, change):
    client, session = contract
    evidence = evidence_payload()
    evidence.update(change)
    store_result(session, {"body_length": 0, "evidence": evidence})
    metadata = client.get("/api/runs/1/results").json()[0]["response_metadata"]
    assert metadata["evidence"] is None
    assert metadata["body_length"] == 0
    assert "canary" not in str(metadata)


@pytest.mark.parametrize("metadata", [
    {}, {"private": "secret-canary"}, {"evidence": None}, {"evidence": []},
    {"evidence": {"schema_version": 1}}, {"body_length": "secret-canary", "body_truncated": 1},
])
def test_historical_malformed_metadata_has_no_invented_evidence(contract, metadata):
    client, session = contract
    store_result(session, metadata)
    assert client.get("/api/runs/1/results").json()[0]["response_metadata"] == {
        "body_length": None, "body_truncated": None, "json_parse_error": None, "evidence": None,
    }


def test_unknown_and_no_match_policy_summaries_preserved(contract):
    client, session = contract
    evidence = evidence_payload()
    evidence.update(policy_decision="UNKNOWN", owner_control_valid=False)
    store_result(session, {"evidence": evidence})
    assert client.get("/api/runs/1/results").json()[0]["response_metadata"]["evidence"] == evidence
    result = session.query(RunResult).filter_by(run_id=1).one()
    evidence.update(policy_id=None, policy_version=None, policy_decision=None, policy_resolution="NO_MATCH")
    result.response_metadata = {"evidence": evidence}
    session.commit()
    assert client.get("/api/runs/1/results").json()[0]["response_metadata"]["evidence"] == evidence
