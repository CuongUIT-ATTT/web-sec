"""One-shot execution from immutable snapshots with batch evidence idempotency."""

from __future__ import annotations

from hashlib import sha256
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.secrets import SecretBox, SecretError
from backend.app.core.settings import Settings
from backend.app.domain.contracts import AuthorizationConclusion, ExecutionStatus, PolicyDecision, RunStatus
from backend.app.persistence.models import BatchCaseClaim, Run, RunExecutionStats, RunIdentitySecret, RunResult
from backend.app.services.findings import record_confirmed_reproduction
from backend.app.scanner.classification.evaluator import Observation, evaluate
from backend.app.scanner.classification.json_pointer import JsonPointerError, resolve_pointer
from backend.app.scanner.classification.policy import PolicyRule, resolve_policy
from backend.app.scanner.execution.http_client import HttpObservation, get_json
from backend.app.workers.queue import complete_run, fail_run, finish_cancellation


def _as_observation(value: HttpObservation) -> Observation:
    return Observation(value.execution_status, value.status_code, value.json_body, value.body_truncated, value.parse_error)


def _concrete_path(template: str, parameter: str, external_id: str) -> str:
    return template.replace("{" + parameter + "}", quote(external_id, safe=""))


def _principal_matches(identity: dict[str, object], observation: HttpObservation) -> bool:
    pointer, expected = identity.get("principal_pointer"), identity.get("expected_principal")
    if (observation.execution_status != ExecutionStatus.COMPLETED_RESPONSE or observation.status_code is None
            or not 200 <= observation.status_code < 300 or not isinstance(pointer, str)
            or not isinstance(expected, str) or observation.json_body is None):
        return False
    try:
        return str(resolve_pointer(observation.json_body, pointer)) == expected
    except JsonPointerError:
        return False


def _payload_fingerprint(*, execution_status: str, conclusion: str, reason_codes: list[str], http_status: int | None, metadata: dict[str, object]) -> str:
    stable = repr((execution_status, conclusion, tuple(reason_codes), http_status, sorted(metadata.items())))
    return sha256(stable.encode("utf-8")).hexdigest()


def _record_batch_result(
    session: Session, *, run: Run, case_key: str, execution_status: str,
    conclusion: str, reason_codes: list[str], http_status: int | None, metadata: dict[str, object],
) -> RunResult | None:
    """Claim a batch case before linking exactly one immutable result."""
    fingerprint = _payload_fingerprint(
        execution_status=execution_status, conclusion=conclusion, reason_codes=reason_codes,
        http_status=http_status, metadata=metadata,
    )
    claim = session.scalar(select(BatchCaseClaim).where(BatchCaseClaim.run_id == run.id, BatchCaseClaim.case_key == case_key))
    if claim is not None:
        if claim.payload_fingerprint != fingerprint:
            fail_run(session, run.id)
            session.flush()
            return None
        return session.get(RunResult, claim.run_result_id) if claim.run_result_id is not None else None
    try:
        with session.begin_nested():
            claim = BatchCaseClaim(run_id=run.id, case_key=case_key, payload_fingerprint=fingerprint)
            session.add(claim)
            session.flush()
    except IntegrityError:
        claim = session.scalar(select(BatchCaseClaim).where(BatchCaseClaim.run_id == run.id, BatchCaseClaim.case_key == case_key))
        if claim is None or claim.payload_fingerprint != fingerprint:
            fail_run(session, run.id)
            return None
        return session.get(RunResult, claim.run_result_id) if claim.run_result_id is not None else None
    result = RunResult(
        run_id=run.id, case_key=case_key, execution_status=execution_status,
        authorization_conclusion=conclusion, reason_codes=reason_codes,
        http_status=http_status, response_metadata=metadata,
    )
    session.add(result)
    session.flush()
    claim.run_result_id = result.id
    session.flush()
    return result


def _cancelled_actor_keys(snapshot: dict[str, object]) -> list[str]:
    identities = snapshot.get("identities", [])
    targets = snapshot.get("targets", [])
    keys: list[str] = []
    if not isinstance(identities, list) or not isinstance(targets, list):
        return keys
    for item in targets:
        if not isinstance(item, dict):
            continue
        operation, resource = item.get("operation"), item.get("resource")
        if not isinstance(operation, dict) or not isinstance(resource, dict):
            continue
        for identity in identities:
            if isinstance(identity, dict):
                keys.append(f"operation:{operation.get('id')}:resource:{resource.get('id')}:actor:{identity.get('id')}")
    return keys


def _cancel_remaining_batch_cases(session: Session, run: Run) -> None:
    stats = session.scalar(select(RunExecutionStats).where(RunExecutionStats.run_id == run.id))
    added = 0
    for case_key in _cancelled_actor_keys(run.snapshot):
        was_missing = session.scalar(select(BatchCaseClaim.id).where(
            BatchCaseClaim.run_id == run.id,
            BatchCaseClaim.case_key == case_key,
        )) is None
        result = _record_batch_result(
            session, run=run, case_key=case_key, execution_status=ExecutionStatus.CANCELLED,
            conclusion=AuthorizationConclusion.NOT_EVALUATED, reason_codes=["execution.cancelled"],
            http_status=None, metadata={},
        )
        if was_missing and result is not None and result.execution_status == ExecutionStatus.CANCELLED:
            added += 1
    if stats is not None:
        stats.cancelled_cases += added
    finish_cancellation(session, run.id)
    session.flush()


async def _tracked_get(
    session: Session, run: Run, stats: RunExecutionStats, *, base_url: str, api_path: str,
    bearer_token: str, settings: Settings, timeout_seconds: float,
) -> HttpObservation | None:
    """Persist numeric wrapper accounting around exactly one no-retry GET call."""
    session.expire(run, ["status"])
    session.refresh(run)
    if run.status == RunStatus.CANCEL_REQUESTED:
        _cancel_remaining_batch_cases(session, run)
        return None
    if run.status != RunStatus.RUNNING or stats.transport_attempts >= stats.planned_attempts:
        return None
    stats.transport_attempts += 1
    # Release the write transaction before awaiting network I/O. This durable
    # checkpoint also lets another connection request cancellation mid-run.
    session.commit()
    observation = await get_json(
        base_url=base_url, api_path=api_path, bearer_token=bearer_token,
        settings=settings, timeout_seconds=timeout_seconds,
    )
    if observation.execution_status in {
        ExecutionStatus.COMPLETED_RESPONSE, ExecutionStatus.BODY_TRUNCATED, ExecutionStatus.JSON_PARSE_ERROR,
    }:
        stats.completed_responses += 1
    elif observation.execution_status == ExecutionStatus.SCOPE_BLOCKED:
        stats.scope_blocked += 1
    elif observation.execution_status in {ExecutionStatus.NETWORK_ERROR, ExecutionStatus.TIMEOUT}:
        stats.transport_errors += 1
    session.flush()
    return observation


async def _execute_single_run(session: Session, run: Run, settings: Settings) -> None:
    """Preserve legacy snapshot support without changing its historical result behavior."""
    snapshot = run.snapshot
    try:
        target, resource, identities, operation, policies = (
            snapshot["target"], snapshot["resource"], snapshot["identities"], snapshot["operation"], snapshot["policies"]
        )
        secrets = {item.identity_id: item for item in session.scalars(select(RunIdentitySecret).where(RunIdentitySecret.run_id == run.id))}
        box = SecretBox.from_key(settings.secret_encryption_key)
        tokens = {int(identity["id"]): box.decrypt_bearer(secrets[int(identity["id"])].ciphertext) for identity in identities}
    except (KeyError, TypeError, ValueError, SecretError):
        fail_run(session, run.id)
        return
    required_requests = len(identities) + 1 + len(identities)
    if required_requests > int(target.get("request_limit", 100)):
        for identity in identities:
            session.add(RunResult(run_id=run.id, case_key=f"resource:{resource['id']}:actor:{identity['id']}", execution_status=ExecutionStatus.REQUEST_LIMIT_REACHED, authorization_conclusion=AuthorizationConclusion.NOT_EVALUATED, reason_codes=["execution.request_limit_reached"], http_status=None, response_metadata={}))
        complete_run(session, run.id)
        return
    verification = {int(identity["id"]): await get_json(base_url=str(target["base_url"]), api_path=str(target["verification_path"]), bearer_token=tokens[int(identity["id"])], settings=settings, timeout_seconds=float(target["timeout_seconds"])) for identity in identities}
    owner_id = int(resource["owner_identity_id"])
    operation_path = _concrete_path(str(operation["path"]), str(resource["path_parameter"]), str(resource["external_id"]))
    baseline = await get_json(base_url=str(target["base_url"]), api_path=operation_path, bearer_token=tokens[owner_id], settings=settings, timeout_seconds=float(target["timeout_seconds"]))
    owner = next((identity for identity in identities if int(identity["id"]) == owner_id), None)
    owner_valid = owner is not None and _principal_matches(owner, verification[owner_id]) and baseline.json_body is not None
    try:
        owner_valid = owner_valid and str(resolve_pointer(baseline.json_body, str(resource["resource_id_pointer"]))) == str(resource["external_id"])
    except JsonPointerError:
        owner_valid = False
    rules = [PolicyRule(int(item["id"]), int(item["version"]), int(item["operation_id"]), int(item["resource_type_id"]), item["identity_id"], item["role"], item["resource_id"], PolicyDecision(item["decision"])) for item in policies]
    for identity in identities:
        response = await get_json(base_url=str(target["base_url"]), api_path=operation_path, bearer_token=tokens[int(identity["id"])], settings=settings, timeout_seconds=float(target["timeout_seconds"]))
        resolution = resolve_policy(rules, operation_id=int(policies[0]["operation_id"]) if policies else -1, resource_type_id=int(resource["resource_type_id"]), identity_id=int(identity["id"]), role=identity.get("role"), resource_id=int(resource["id"]))
        evaluation = evaluate(policy_status=resolution.status, policy_decision=resolution.rule.decision if resolution.rule else None, identity_confirmed=_principal_matches(identity, verification[int(identity["id"])]), owner_control_valid=owner_valid, requested_resource_id=str(resource["external_id"]), resource_pointer=str(resource["resource_id_pointer"]), restricted_pointers=tuple(resource["restricted_pointers"]), owner_body=baseline.json_body, observation=_as_observation(response))
        result = RunResult(run_id=run.id, case_key=f"resource:{resource['id']}:actor:{identity['id']}", execution_status=response.execution_status, authorization_conclusion=evaluation.conclusion, reason_codes=list(evaluation.reason_codes), http_status=response.status_code, response_metadata={"body_length": response.body_length, "body_truncated": response.body_truncated, "json_parse_error": response.parse_error})
        session.add(result); session.flush()
        if evaluation.conclusion == AuthorizationConclusion.CONFIRMED_VIOLATION and resolution.rule is not None:
            record_confirmed_reproduction(session, project_id=run.project_id, run_result=result, actor_identity_id=int(identity["id"]), resource_id=int(resource["id"]), operation_path=str(operation["path"]), resource_pointer=str(resource["resource_id_pointer"]), restricted_pointers=tuple(resource["restricted_pointers"]), policy=resolution.rule)
    complete_run(session, run.id)


async def _execute_batch_run(session: Session, run: Run, settings: Settings) -> None:
    snapshot = run.snapshot
    target, identities, targets, plan = snapshot.get("target"), snapshot.get("identities"), snapshot.get("targets"), snapshot.get("request_plan")
    if not isinstance(target, dict) or not isinstance(identities, list) or not isinstance(targets, list) or not isinstance(plan, dict) or not identities or not targets:
        fail_run(session, run.id); return
    expected = len(identities) + len(targets) + len(identities) * len(targets)
    planned = plan.get("planned_attempts", plan.get("maximum_http_requests"))
    if any((plan.get("identity_verifications") != len(identities), plan.get("owner_baselines") != len(targets), plan.get("actor_cases") != len(identities) * len(targets), planned != expected)):
        fail_run(session, run.id); return
    stats = session.scalar(select(RunExecutionStats).where(RunExecutionStats.run_id == run.id))
    if stats is None:
        stats = RunExecutionStats(run_id=run.id, planned_attempts=expected)
        session.add(stats); session.flush()
    if stats.planned_attempts != expected:
        fail_run(session, run.id); return
    try:
        secrets = {item.identity_id: item for item in session.scalars(select(RunIdentitySecret).where(RunIdentitySecret.run_id == run.id))}
        box = SecretBox.from_key(settings.secret_encryption_key)
        tokens = {int(identity["id"]): box.decrypt_bearer(secrets[int(identity["id"])].ciphertext) for identity in identities}
        request_limit = int(target["request_limit"])
    except (KeyError, TypeError, ValueError, SecretError):
        fail_run(session, run.id); return
    if expected > request_limit:
        for case_key in _cancelled_actor_keys(snapshot):
            _record_batch_result(session, run=run, case_key=case_key, execution_status=ExecutionStatus.REQUEST_LIMIT_REACHED, conclusion=AuthorizationConclusion.NOT_EVALUATED, reason_codes=["execution.request_limit_reached"], http_status=None, metadata={})
        complete_run(session, run.id); return
    verification: dict[int, HttpObservation] = {}
    for identity in identities:
        observation = await _tracked_get(session, run, stats, base_url=str(target["base_url"]), api_path=str(target["verification_path"]), bearer_token=tokens[int(identity["id"])], settings=settings, timeout_seconds=float(target["timeout_seconds"]))
        if observation is None: return
        verification[int(identity["id"])] = observation
    for item in targets:
        if not isinstance(item, dict): fail_run(session, run.id); return
        operation, resource, policies = item.get("operation"), item.get("resource"), item.get("policies")
        if not isinstance(operation, dict) or not isinstance(resource, dict) or not isinstance(policies, list) or operation.get("method") != "GET":
            fail_run(session, run.id); return
        try:
            owner_id, operation_id, resource_id, resource_type_id = int(resource["owner_identity_id"]), int(operation["id"]), int(resource["id"]), int(resource["resource_type_id"])
            owner = next(identity for identity in identities if int(identity["id"]) == owner_id)
            operation_path = _concrete_path(str(operation["path"]), str(resource["path_parameter"]), str(resource["external_id"]))
            if "{" + str(resource["path_parameter"]) + "}" not in str(operation["path"]): raise ValueError
            rules = [PolicyRule(int(policy["id"]), int(policy["version"]), int(policy["operation_id"]), int(policy["resource_type_id"]), policy.get("identity_id"), policy.get("role"), policy.get("resource_id"), PolicyDecision(policy["decision"])) for policy in policies]
        except (KeyError, TypeError, ValueError, StopIteration):
            fail_run(session, run.id); return
        baseline = await _tracked_get(session, run, stats, base_url=str(target["base_url"]), api_path=operation_path, bearer_token=tokens[owner_id], settings=settings, timeout_seconds=float(target["timeout_seconds"]))
        if baseline is None: return
        owner_valid = _principal_matches(owner, verification[owner_id]) and baseline.json_body is not None
        try: owner_valid = owner_valid and str(resolve_pointer(baseline.json_body, str(resource["resource_id_pointer"]))) == str(resource["external_id"])
        except JsonPointerError: owner_valid = False
        for identity in identities:
            response = await _tracked_get(session, run, stats, base_url=str(target["base_url"]), api_path=operation_path, bearer_token=tokens[int(identity["id"])], settings=settings, timeout_seconds=float(target["timeout_seconds"]))
            if response is None: return
            identity_id = int(identity["id"])
            resolution = resolve_policy(rules, operation_id=operation_id, resource_type_id=resource_type_id, identity_id=identity_id, role=identity.get("role") if isinstance(identity.get("role"), str) else None, resource_id=resource_id)
            evaluation = evaluate(policy_status=resolution.status, policy_decision=resolution.rule.decision if resolution.rule else None, identity_confirmed=_principal_matches(identity, verification[identity_id]), owner_control_valid=owner_valid, requested_resource_id=str(resource["external_id"]), resource_pointer=str(resource["resource_id_pointer"]), restricted_pointers=tuple(resource["restricted_pointers"]), owner_body=baseline.json_body, observation=_as_observation(response))
            result = _record_batch_result(session, run=run, case_key=f"operation:{operation_id}:resource:{resource_id}:actor:{identity_id}", execution_status=response.execution_status, conclusion=evaluation.conclusion, reason_codes=list(evaluation.reason_codes), http_status=response.status_code, metadata={"body_length": response.body_length, "body_truncated": response.body_truncated, "json_parse_error": response.parse_error})
            if result is None: return
            if evaluation.conclusion == AuthorizationConclusion.CONFIRMED_VIOLATION and resolution.rule is not None:
                record_confirmed_reproduction(session, project_id=run.project_id, run_result=result, actor_identity_id=identity_id, resource_id=resource_id, operation_path=str(operation["path"]), resource_pointer=str(resource["resource_id_pointer"]), restricted_pointers=tuple(resource["restricted_pointers"]), policy=resolution.rule)
    if not complete_run(session, run.id):
        # A cancellation can win after the final observed actor response. Do
        # not overwrite it with completion; finalize the pending cancellation
        # without dispatching another request.
        session.expire(run, ["status"])
        session.refresh(run)
        if run.status == RunStatus.CANCEL_REQUESTED:
            _cancel_remaining_batch_cases(session, run)
    session.flush()


async def execute_run(session: Session, run: Run, settings: Settings) -> bool:
    """Execute only a durably claimed RUNNING run; terminal/replayed calls are no-ops."""
    session.refresh(run)
    if run.status != RunStatus.RUNNING:
        return False
    if run.snapshot.get("run_kind") == "BATCH_ALL_SELECTED":
        await _execute_batch_run(session, run, settings)
    else:
        await _execute_single_run(session, run, settings)
    return True
