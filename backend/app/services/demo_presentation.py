"""Public research DTOs. Never mutate or return internal execution snapshots."""
from backend.app.domain.contracts import PolicyDecision
from backend.app.scanner.classification.policy import PolicyRule, resolve_policy
from backend.app.scanner.matrix.generator import generate_cases


def matrix_rows(operation, resource, identities, policies):
    by_id = {identity.id: identity for identity in identities}
    owner = by_id[resource.owner_identity_id]
    rules = [PolicyRule(p.id, p.version, p.operation_id, p.resource_type_id,
                        p.identity_id, p.role, p.resource_id, PolicyDecision(p.decision)) for p in policies]
    resolutions = {i.id: resolve_policy(rules, operation_id=operation.id,
        resource_type_id=resource.resource_type_id, identity_id=i.id,
        role=i.role, resource_id=resource.id) for i in identities}
    cases = generate_cases(resource_id=resource.id, owner_identity_id=owner.id,
        actor_identity_ids=by_id, resolutions=resolutions, verified_identity_ids=set(),
        operation_id=operation.id)
    rows = []
    for case in cases:
        actor = by_id[case.actor_identity_id]
        rule = resolutions[actor.id].rule
        rows.append(dict(case_key=case.case_key, control_type=case.control_type,
            actor_identity_id=actor.id, actor_alias=f"identity-{actor.id}", actor_role=actor.role,
            resource_id=resource.id, resource_alias=f"resource-{resource.id}",
            owner_identity_id=owner.id, owner_alias=f"identity-{owner.id}", owner_role=owner.role,
            ownership_category="OWNER" if actor.id == owner.id else "CROSS_USER" if actor.role == owner.role else "CROSS_ROLE",
            operation_id=operation.id, method=operation.method, path_template=operation.path,
            policy_status=case.policy_status, resolved_decision=rule.decision if rule else None,
            expected_decision=rule.decision if rule else "UNKNOWN",
            policy_id=rule.id if rule else None, policy_version=rule.version if rule else None,
            warnings=list(case.warnings)))
    return rows


def public_snapshot(snapshot):
    """Count-only allowlist works for legacy and batch snapshots, including unknown versions."""
    if not isinstance(snapshot, dict):
        return {"presentation_version": 1}
    identities = snapshot.get("identities")
    targets = snapshot.get("targets")
    plan = snapshot.get("request_plan")
    safe_plan = {key: plan[key] for key in (
        "identity_verifications", "owner_baselines", "actor_cases", "planned_attempts", "maximum_http_requests")
        if isinstance(plan, dict) and type(plan.get(key)) is int and plan[key] >= 0}
    if snapshot.get("run_kind") == "AUTOAUTH_SELECTED":
        metadata = snapshot.get("display_metadata", {})
        names = {i["id"]: i for i in metadata.get("identities", [])}
        legacy_roles = {i["id"]: i.get("role") for i in snapshot.get("identities", [])}
        resource_names = {r["id"]: r.get("display_name") for r in metadata.get("resources", [])}
        def label(identity_id):
            i = names.get(identity_id, {})
            return dict(id=identity_id, display_name=i.get("display_name"),
                        role=i.get("role") or legacy_roles.get(identity_id),
                        source="SNAPSHOT" if i else "LEGACY_UNAVAILABLE")
        summaries = [dict(case_id=c["case_id"], actor=label(c["actor_identity_id"]),
            owner=label(c.get("owner_identity_id")), baseline=label(c.get("baseline_identity_id")),
            method=c.get("method"), path=c.get("path_template"),
            resource_name=resource_names.get(c.get("resource_id")), resource_id=c.get("resource_id"))
            for c in snapshot.get("cases", [])]
        return {"presentation_version": 1, "run_kind": "AUTOAUTH_SELECTED",
            "identity_count": len(identities) if isinstance(identities, list) else 0,
            "concrete_target_count": len(snapshot.get("cases", [])), "request_plan": safe_plan,
            "policy_revision": snapshot.get("policy_revision"), "case_summaries": summaries}
    return {"presentation_version": 1,
        "run_kind": "BATCH_ALL_SELECTED" if snapshot.get("run_kind") == "BATCH_ALL_SELECTED" else "SINGLE",
        "identity_count": len(identities) if isinstance(identities, list) else 0,
        "concrete_target_count": len(targets) if isinstance(targets, list) else int(isinstance(snapshot.get("resource"), dict)),
        "request_plan": safe_plan}
