"""GET-only execution of queue-time reusable-policy snapshots."""
from sqlalchemy import select
from backend.app.core.secrets import SecretBox, SecretError
from backend.app.domain.contracts import AuthorizationConclusion, ExecutionStatus, RunStatus
from backend.app.persistence.models import RunIdentitySecret, RunExecutionStats, RunResult
from backend.app.scanner.classification.evaluator import evaluate_authorization_case
from backend.app.workers.queue import complete_run, fail_run


async def execute_authorization_run(session, run, settings):
    # Local import avoids a cycle while reusing transport accounting/cancellation.
    from backend.app.workers.runner import (_tracked_get, _principal_matches,
        _owner_control_valid, _concrete_path, _as_observation, _record_batch_result,
        _cancel_remaining_batch_cases, _resource_matches)
    from backend.app.scanner.classification.evaluator import restricted_fields_match
    snapshot = run.snapshot
    try:
        cases, target = snapshot["cases"], snapshot["target"]
        identities = {i["id"]: i for i in snapshot["identities"]}
        baselines = {(c["operation_id"], c["resource_id"], c["baseline_identity_id"]) for c in cases}
        expected = len(identities) + len(baselines) + len(cases)
        stats = session.scalar(select(RunExecutionStats).where(RunExecutionStats.run_id == run.id))
        if (not cases or len({c["case_id"] for c in cases}) != len(cases) or
                any(c["operation"]["method"] != "GET" or not c["execution_eligible"] for c in cases) or
                expected != snapshot["request_plan"]["planned_attempts"] or
                expected > target["request_limit"] or stats is None or stats.planned_attempts != expected):
            raise ValueError("Invalid plan")
        # A prior durable dispatch checkpoint is uncertain work; never replay it.
        if stats.transport_attempts or session.scalar(select(RunResult.id).where(RunResult.run_id == run.id)):
            fail_run(session, run.id)
            return
        secrets = {s.identity_id: s for s in session.scalars(select(RunIdentitySecret).where(RunIdentitySecret.run_id == run.id))}
        box = SecretBox.from_key(settings.secret_encryption_key)
        tokens = {i: box.decrypt_bearer(secrets[i].ciphertext) for i in identities}
        if any(c["actor_identity_id"] not in identities or c["baseline_identity_id"] not in identities for c in cases):
            raise ValueError("Missing identity")
    except (KeyError, TypeError, ValueError, SecretError):
        fail_run(session, run.id)
        return

    async def get(identity_id, path):
        return await _tracked_get(session, run, stats, base_url=target["base_url"], api_path=path,
            bearer_token=tokens[identity_id], settings=settings, timeout_seconds=target["timeout_seconds"])

    verification = {}
    for identity_id in identities:
        response = await get(identity_id, target["verification_path"])
        if response is None:
            return
        verification[identity_id] = response
    observed_baselines = {}
    for case in cases:
        actor_id, baseline_id = case["actor_identity_id"], case["baseline_identity_id"]
        resource = case.get("resource")
        path = (_concrete_path(case["operation"]["path"], resource["path_parameter"], resource["external_id"])
                if resource else case["operation"]["path"])
        # No unresolved placeholders may leave this adapter.
        if "{" in path or "}" in path:
            fail_run(session, run.id)
            return
        key = (case["operation_id"], case["resource_id"], baseline_id)
        if key not in observed_baselines:
            baseline = await get(baseline_id, path)
            if baseline is None:
                return
            observed_baselines[key] = baseline
        baseline = observed_baselines[key]
        baseline_resource = resource
        if case["kind"] == "BFLA":
            contract = case.get("observation_contract") or {}
            baseline_resource = dict(external_id=contract.get("result_value"),
                resource_id_pointer=contract.get("result_pointer", ""),
                restricted_pointers=contract.get("protected_pointers", []))
        valid = _owner_control_valid(identities[baseline_id], verification[baseline_id], baseline, baseline_resource)
        response = await get(actor_id, path)
        if response is None:
            return
        evaluation = evaluate_authorization_case(case=case,
            identity_confirmed=_principal_matches(identities[actor_id], verification[actor_id]),
            baseline_valid=valid, baseline_body=baseline.json_body, observation=_as_observation(response))
        # Allowlisted booleans and IDs only. No raw response values or credentials.
        metadata = dict(body_length=response.body_length, body_truncated=response.body_truncated,
            json_parse_error=response.parse_error, evidence=dict(schema_version=3,
                engine="autoauth-evaluator-v1", case_id=case["case_id"], run_id=run.id,
                kind=case["kind"], policy_revision=case["policy_revision"],
                matched_rule_keys=case["matched_rule_keys"], expected_decision=case["expected_decision"],
                actor_identity_id=actor_id, baseline_identity_id=baseline_id,
                baseline_authorized=True, baseline_valid=valid, baseline_http_status=baseline.status_code,
                baseline_resource_matches=_resource_matches(baseline.json_body, baseline_resource),
                actor_resource_matches=_resource_matches(response.json_body, baseline_resource),
                protected_fields_match_baseline=restricted_fields_match(baseline.json_body,
                    response.json_body, tuple(baseline_resource["restricted_pointers"])),
                actor_body_truncated=response.body_truncated, actor_json_parse_error=response.parse_error,
                baseline_body_truncated=baseline.body_truncated, baseline_json_parse_error=baseline.parse_error,
                actor_principal_matches=_principal_matches(identities[actor_id], verification[actor_id])))
        _record_batch_result(session, run=run, case_key=case["case_id"],
            execution_status=response.execution_status, conclusion=evaluation.conclusion,
            reason_codes=list(evaluation.reason_codes), http_status=response.status_code, metadata=metadata)
        # Preserve completed case evidence before any subsequent dispatch/checkpoint.
        session.commit()
    if not complete_run(session, run.id):
        session.refresh(run)
        if run.status == RunStatus.CANCEL_REQUESTED:
            _cancel_remaining_batch_cases(session, run)
    session.flush()
