"""Authenticated configuration, preview and explicitly selected GET queue API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.api.routes import get_session
from backend.app.api.workflow_routes import require_project
from backend.app.core.auth import require_admin, require_csrf
from backend.app.persistence.models import ProjectAuthorizationRevision, Target, OpenApiOperation
from backend.app.api.workflow_schemas import OpenApiImport
from backend.app.scanner.openapi.parser import parse_openapi_json, OpenApiError
from backend.app.services.authorization_model import (AuthorizationConfig, configuration_rows,
    validate_references, revision, preview)

from backend.app.services.authorization_execution import SelectedAuthorizationCases, selected_snapshot, queue_selected, public_authorization_conclusion

router = APIRouter(prefix="/api/projects/{project_id}/authorization", tags=["authorization-model"])


def current(session, project_id):
    return session.scalar(select(ProjectAuthorizationRevision).where(ProjectAuthorizationRevision.project_id == project_id).order_by(ProjectAuthorizationRevision.id.desc()).limit(1))


@router.get("/config", dependencies=[Depends(require_admin)])
def read_config(project_id: int, session: Session = Depends(get_session)):
    require_project(session, project_id)
    row = current(session, project_id)
    return {"revision": row.revision if row else None, "configuration": row.configuration if row else AuthorizationConfig().model_dump(), "legacy_unchanged": True}


@router.put("/config", dependencies=[Depends(require_csrf)])
def write_config(project_id: int, payload: AuthorizationConfig, session: Session = Depends(get_session)):
    require_project(session, project_id)
    try:
        validate_references(payload, *configuration_rows(session, project_id))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    digest = revision(payload)
    previous = current(session, project_id)
    # Repeating the current configuration is idempotent; reverting to an earlier
    # revision is rejected explicitly instead of silently returning a different head.
    if previous and previous.revision == digest:
        return {"revision": digest, "configuration": previous.configuration}
    row = ProjectAuthorizationRevision(project_id=project_id, revision=digest, configuration=payload.model_dump())
    session.add(row)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(409, "Revision already exists; current configuration was preserved") from error
    return {"revision": digest, "configuration": row.configuration}


@router.get("/preview", dependencies=[Depends(require_admin)])
def config_preview(project_id: int, target_id: int, session: Session = Depends(get_session)):
    require_project(session, project_id)
    target = session.get(Target, target_id)
    if target is None or target.project_id != project_id:
        raise HTTPException(404, "Target does not belong to project")
    row = current(session, project_id)
    config = AuthorizationConfig.model_validate(row.configuration) if row else AuthorizationConfig()
    try:
        return preview(session, project_id, target, config)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/openapi", dependencies=[Depends(require_csrf)])
def import_inventory(project_id: int, payload: OpenApiImport, session: Session = Depends(get_session)):
    """Inventory all methods, default disabled; does not change legacy import behavior."""
    require_project(session, project_id)
    try:
        inventory = parse_openapi_json(payload.document, include_non_get=True)
    except OpenApiError as error:
        raise HTTPException(422, str(error)) from error
    existing = list(session.scalars(select(OpenApiOperation).where(OpenApiOperation.project_id == project_id)))
    pairs = {(o.method, o.path) for o in existing}
    keys = {o.operation_key for o in existing}
    for item in inventory:
        if (item.method, item.path) in pairs:
            continue
        key = f"{item.method}:{item.path}"
        if len(key) > 200 or key in keys:
            raise HTTPException(422, "Ambiguous or oversized operation key")
        session.add(OpenApiOperation(project_id=project_id, operation_key=key, method=item.method, path=item.path, selected=False))
        keys.add(key)
        pairs.add((item.method, item.path))
    session.commit()
    return [dict(id=o.id, method=o.method, path=o.path, selected=o.selected) for o in session.scalars(select(OpenApiOperation).where(OpenApiOperation.project_id == project_id).order_by(OpenApiOperation.id))]


@router.post("/runs", dependencies=[Depends(require_csrf)], status_code=201)
def queue_authorization(project_id: int, payload: "SelectedAuthorizationCases", session: Session = Depends(get_session)):
    require_project(session, project_id)
    target = session.get(Target, payload.target_id)
    if target is None or target.project_id != project_id:
        raise HTTPException(404, "Target does not belong to project")
    row = current(session, project_id)
    if row is None:
        raise HTTPException(422, "Missing authorization configuration")
    try:
        snapshot = selected_snapshot(session, project_id, target,
            AuthorizationConfig.model_validate(row.configuration), payload)
        run = queue_selected(session, project_id, snapshot)
    except ValueError as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error
    return {"id": run.id, "status": run.status, "policy_revision": snapshot["policy_revision"],
        "case_ids": [c["case_id"] for c in snapshot["cases"]], "request_plan": snapshot["request_plan"]}


@router.get("/runs/{run_id}/results", dependencies=[Depends(require_admin)])
def authorization_results(project_id: int, run_id: int, session: Session = Depends(get_session)):
    from backend.app.persistence.models import Run, RunResult
    run = session.get(Run, run_id)
    if run is None or run.project_id != project_id or run.snapshot.get("run_kind") != "AUTOAUTH_SELECTED":
        raise HTTPException(404, "Authorization run not found")
    results = {r.case_key: r for r in session.scalars(select(RunResult).where(RunResult.run_id == run.id))}
    rows = []
    # Labels are queue-time metadata only. Never query mutable project identities here.
    display = run.snapshot.get("display_metadata", {})
    labels = {i["id"]: i for i in display.get("identities", [])}
    legacy_roles = {i["id"]: i.get("role") for i in run.snapshot.get("identities", [])}
    resources = {r["id"]: r for r in display.get("resources", [])}
    def identity_label(identity_id):
        item = labels.get(identity_id)
        return dict(id=identity_id, display_name=item.get("display_name") if item else None,
                    role=(item.get("role") if item else None) or legacy_roles.get(identity_id), source="SNAPSHOT" if item else "LEGACY_UNAVAILABLE")
    for case in run.snapshot["cases"]:
        result = results.get(case["case_id"])
        observed = (result.response_metadata or {}).get("evidence", {}) if result else {}
        actual_id = observed.get("baseline_identity_id")
        owner_id = case.get("owner_identity_id", (case.get("resource") or {}).get("owner_identity_id"))
        rows.append(dict(case_id=case["case_id"], run_id=run.id,
            result_id=result.id if result else None,
            presentation=dict(actor=identity_label(case["actor_identity_id"]),
                owner=identity_label(owner_id), planned_baseline=identity_label(case["baseline_identity_id"]),
                actual_baseline=identity_label(actual_id),
                resource_name=resources.get(case["resource_id"], {}).get("display_name"),
                method=case.get("method", (case.get("operation") or {}).get("method")),
                path=case.get("path_template", (case.get("operation") or {}).get("path")),
                relationship=case.get("relationship"),
                baseline_kind=case.get("baseline_kind"),
                baseline_provenance="OBSERVED_EVIDENCE" if actual_id is not None else "NOT_OBSERVED"),
            finding_id=f"autoauth-result:{result.id}" if result and result.authorization_conclusion in {"CONFIRMED_VIOLATION", "SUSPECTED_VIOLATION"} else None,
            artifact_ref=f"run:{run.id}:result:{result.id}" if result else None,
            policy_revision=case["policy_revision"], matched_rule_keys=case["matched_rule_keys"],
            kind=case["kind"], operation_id=case["operation_id"],
            actor_identity_id=case["actor_identity_id"], resource_id=case["resource_id"],
            baseline_identity_id=case["baseline_identity_id"], expected_decision=case["expected_decision"],
            execution_status=result.execution_status if result else "NOT_RUN",
            conclusion=public_authorization_conclusion(result),
            reason_codes=result.reason_codes if result else ["execution.not_observed"],
            http_status=result.http_status if result else None,
            evidence={key: result.response_metadata.get("evidence", {}).get(key) for key in (
                "baseline_authorized", "baseline_valid", "baseline_http_status", "actor_principal_matches",
                "baseline_resource_matches", "actor_resource_matches", "protected_fields_match_baseline",
                "actor_body_truncated", "actor_json_parse_error", "baseline_body_truncated", "baseline_json_parse_error")}
                if result else None))
    return dict(run_id=run.id, status=run.status, policy_revision=run.snapshot["policy_revision"], cases=rows)
