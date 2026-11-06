"""One-shot run execution using only immutable run configuration and private token copies."""

from __future__ import annotations

from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.secrets import SecretBox, SecretError
from backend.app.core.settings import Settings
from backend.app.domain.contracts import AuthorizationConclusion, PolicyDecision, RunStatus
from backend.app.persistence.models import Run, RunIdentitySecret, RunResult
from backend.app.services.findings import record_confirmed_reproduction
from backend.app.scanner.classification.evaluator import Observation, evaluate
from backend.app.scanner.classification.json_pointer import JsonPointerError, resolve_pointer
from backend.app.scanner.classification.policy import PolicyRule, resolve_policy
from backend.app.scanner.execution.http_client import HttpObservation, get_json


def _as_observation(value: HttpObservation) -> Observation:
    return Observation(
        execution_status=value.execution_status,
        status_code=value.status_code,
        json_body=value.json_body,
        body_truncated=value.body_truncated,
        parse_error=value.parse_error,
    )


def _concrete_path(template: str, parameter: str, external_id: str) -> str:
    return template.replace("{" + parameter + "}", quote(external_id, safe=""))


def _principal_matches(identity: dict[str, object], observation: HttpObservation) -> bool:
    pointer = identity.get("principal_pointer")
    expected = identity.get("expected_principal")
    if (
        observation.execution_status.value != "COMPLETED_RESPONSE"
        or observation.status_code is None
        or not 200 <= observation.status_code < 300
        or not isinstance(pointer, str)
        or not isinstance(expected, str)
        or observation.json_body is None
    ):
        return False
    try:
        return str(resolve_pointer(observation.json_body, pointer)) == expected
    except JsonPointerError:
        return False


async def execute_run(session: Session, run: Run, settings: Settings) -> None:
    """Run fresh identity and owner controls before each configured actor case."""
    snapshot = run.snapshot
    target = snapshot["target"]
    resource = snapshot["resource"]
    identities = snapshot["identities"]
    operation = snapshot["operation"]
    policies = snapshot["policies"]
    secrets = {item.identity_id: item for item in session.scalars(select(RunIdentitySecret).where(RunIdentitySecret.run_id == run.id))}
    box = SecretBox.from_key(settings.secret_encryption_key)
    tokens: dict[int, str] = {}
    try:
        for identity in identities:
            identity_id = int(identity["id"])
            tokens[identity_id] = box.decrypt_bearer(secrets[identity_id].ciphertext)
    except (KeyError, SecretError):
        run.status = RunStatus.FAILED
        session.flush()
        return
    required_requests = len(identities) + 1 + len(identities)
    request_limit = int(target.get("request_limit", 100))
    if required_requests > request_limit:
        for identity in identities:
            session.add(RunResult(
                run_id=run.id,
                case_key=f"resource:{resource['id']}:actor:{identity['id']}",
                execution_status="REQUEST_LIMIT_REACHED",
                authorization_conclusion=AuthorizationConclusion.NOT_EVALUATED,
                reason_codes=["execution.request_limit_reached"],
                http_status=None,
                response_metadata={},
            ))
        run.status = RunStatus.COMPLETED
        session.flush()
        return
    verification: dict[int, HttpObservation] = {}
    for identity in identities:
        identity_id = int(identity["id"])
        verification[identity_id] = await get_json(
            base_url=str(target["base_url"]),
            api_path=str(target["verification_path"]),
            bearer_token=tokens[identity_id],
            settings=settings,
            timeout_seconds=float(target["timeout_seconds"]),
        )
    owner_id = int(resource["owner_identity_id"])
    operation_path = _concrete_path(str(operation["path"]), str(resource["path_parameter"]), str(resource["external_id"]))
    owner_baseline = await get_json(
        base_url=str(target["base_url"]),
        api_path=operation_path,
        bearer_token=tokens[owner_id],
        settings=settings,
        timeout_seconds=float(target["timeout_seconds"]),
    )
    owner_identity = next((identity for identity in identities if int(identity["id"]) == owner_id), None)
    owner_control_valid = owner_identity is not None and _principal_matches(owner_identity, verification[owner_id]) and owner_baseline.json_body is not None
    try:
        owner_control_valid = owner_control_valid and str(resolve_pointer(owner_baseline.json_body, str(resource["resource_id_pointer"]))) == str(resource["external_id"])
    except JsonPointerError:
        owner_control_valid = False
    policy_rules = [
        PolicyRule(int(item["id"]), int(item["version"]), int(item["operation_id"]), int(item["resource_type_id"]), item["identity_id"], item["role"], item["resource_id"], PolicyDecision(item["decision"]))
        for item in policies
    ]
    for identity in identities:
        if run.status == RunStatus.CANCEL_REQUESTED:
            run.status = RunStatus.CANCELLED
            break
        identity_id = int(identity["id"])
        response = await get_json(
            base_url=str(target["base_url"]),
            api_path=operation_path,
            bearer_token=tokens[identity_id],
            settings=settings,
            timeout_seconds=float(target["timeout_seconds"]),
        )
        resolution = resolve_policy(
            policy_rules,
            operation_id=int(policies[0]["operation_id"]) if policies else -1,
            resource_type_id=int(resource["resource_type_id"]),
            identity_id=identity_id,
            role=identity.get("role") if isinstance(identity.get("role"), str) else None,
            resource_id=int(resource["id"]),
        )
        result = evaluate(
            policy_status=resolution.status,
            policy_decision=resolution.rule.decision if resolution.rule else None,
            identity_confirmed=_principal_matches(identity, verification[identity_id]),
            owner_control_valid=owner_control_valid,
            requested_resource_id=str(resource["external_id"]),
            resource_pointer=str(resource["resource_id_pointer"]),
            restricted_pointers=tuple(resource["restricted_pointers"]),
            owner_body=owner_baseline.json_body,
            observation=_as_observation(response),
        )
        run_result = RunResult(
            run_id=run.id,
            case_key=f"resource:{resource['id']}:actor:{identity_id}",
            execution_status=response.execution_status,
            authorization_conclusion=result.conclusion,
            reason_codes=list(result.reason_codes),
            http_status=response.status_code,
            response_metadata={"body_length": response.body_length, "body_truncated": response.body_truncated, "json_parse_error": response.parse_error},
        )
        session.add(run_result)
        session.flush()
        if result.conclusion == AuthorizationConclusion.CONFIRMED_VIOLATION and resolution.rule is not None:
            record_confirmed_reproduction(
                session,
                project_id=run.project_id,
                run_result=run_result,
                actor_identity_id=identity_id,
                resource_id=int(resource["id"]),
                operation_path=str(operation["path"]),
                resource_pointer=str(resource["resource_id_pointer"]),
                restricted_pointers=tuple(resource["restricted_pointers"]),
                policy=resolution.rule,
            )
    if run.status == RunStatus.RUNNING:
        run.status = RunStatus.COMPLETED
    session.flush()
