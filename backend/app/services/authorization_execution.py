"""Explicit selection adapter for reusable authorization revisions; no network I/O."""
from copy import deepcopy
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from backend.app.persistence.models import (IdentitySecret, Run, RunIdentitySecret, RunExecutionStats)
from backend.app.services.authorization_model import configuration_rows, preview, revision
from backend.app.services.run_snapshot import _identity_snapshot, _target_snapshot


class SelectedAuthorizationCases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_id: int
    policy_revision: str
    case_ids: list[str] = Field(min_length=1, max_length=10000)


def selected_snapshot(session, project_id, target, config, payload):
    """Reject stale/invalid selections as a whole, never silently narrow a selection."""
    matrix = preview(session, project_id, target, config)
    if payload.policy_revision != revision(config):
        raise ValueError("STALE_POLICY_REVISION")
    if len(payload.case_ids) != len(set(payload.case_ids)):
        raise ValueError("DUPLICATE_CASE_SELECTION")
    rows = {c["case_id"]: c for c in matrix["cases"]}
    if any(key not in rows for key in payload.case_ids):
        raise ValueError("UNKNOWN_CASE_SELECTION")
    cases = [deepcopy(rows[key]) for key in sorted(payload.case_ids)]
    if any(not c["execution_eligible"] for c in cases):
        raise ValueError("NON_EXECUTABLE_CASE_SELECTION")
    identities, operations, types, resources = configuration_rows(session, project_id)
    ops, rtypes, objs = ({x.id: x for x in values} for values in (operations, types, resources))
    approvals = {a.operation_id: a for a in config.operations}
    for case in cases:
        operation = ops[case["operation_id"]]
        case["operation"] = {"id": operation.id, "path": operation.path, "method": operation.method}
        if case["resource_id"] is not None:
            resource = objs[case["resource_id"]]
            resource_type = rtypes[resource.resource_type_id]
            case["resource"] = dict(id=resource.id, external_id=resource.external_id,
                owner_identity_id=resource.owner_identity_id, path_parameter=resource.path_parameter,
                resource_id_pointer=resource_type.resource_id_pointer,
                restricted_pointers=resource_type.restricted_pointers)
        case["observation_contract"] = approvals[operation.id].model_dump().get("evidence")
    baselines = {(c["operation_id"], c["resource_id"], c["baseline_identity_id"]) for c in cases}
    needed = {c["actor_identity_id"] for c in cases} | {b[2] for b in baselines}
    budget = len(needed) + len(baselines) + len(cases)
    if budget > target.request_limit:
        raise ValueError("REQUEST_LIMIT_EXCEEDED")
    return dict(schema_version=3, run_kind="AUTOAUTH_SELECTED", target=_target_snapshot(target),
        policy_revision=matrix["policy_revision"], configuration=config.model_dump(),
        display_metadata=dict(version=1,
            identities=[dict(id=i.id, display_name=i.display_name, role=i.role) for i in identities],
            resources=[dict(id=r.id, display_name=f"resource-{r.id}", owner_identity_id=r.owner_identity_id) for r in resources]),
        cases=cases, identities=[_identity_snapshot(i) for i in identities if i.id in needed],
        request_plan=dict(identity_verifications=len(needed), owner_baselines=len(baselines),
            actor_cases=len(cases), planned_attempts=budget))


def queue_selected(session, project_id, snapshot):
    run = Run(project_id=project_id, status="QUEUED", snapshot=snapshot)
    session.add(run)
    session.flush()
    for identity in snapshot["identities"]:
        secret = session.scalar(select(IdentitySecret).where(IdentitySecret.identity_id == identity["id"]))
        if secret is None:
            raise ValueError("MISSING_QUEUE_CREDENTIAL")
        session.add(RunIdentitySecret(run_id=run.id, identity_id=identity["id"],
            ciphertext=secret.ciphertext, key_version=secret.key_version))
    session.add(RunExecutionStats(run_id=run.id, planned_attempts=snapshot["request_plan"]["planned_attempts"]))
    session.commit()
    return run


def public_authorization_conclusion(result):
    """Project historical rows into the six-result API without rewriting storage.

    Missing rows and pre-dispatch terminal states have no actor observation.
    Transport errors/partial responses remain evidence-insufficient, never PASS.
    """
    if result is None:
        return "NOT_RUN"
    if result.authorization_conclusion in {
        "CONFIRMED_VIOLATION", "SUSPECTED_VIOLATION", "POLICY_CONSISTENT_CASE",
        "INVALID_TEST", "INSUFFICIENT_EVIDENCE", "NOT_RUN",
    }:
        return result.authorization_conclusion
    if (result.execution_status in {"CANCELLED", "REQUEST_LIMIT_REACHED", "SCOPE_BLOCKED"}
            and result.http_status is None and not result.response_metadata):
        return "NOT_RUN"
    return "INSUFFICIENT_EVIDENCE"
