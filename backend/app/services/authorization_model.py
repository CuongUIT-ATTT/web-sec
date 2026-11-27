"""Network-free project authorization configuration and deterministic preview contract.

Legacy execution remains separate. Preview is never authority for dispatch:
explicit selection and queue-time snapshots are required; writes stay excluded.
"""
from hashlib import sha256
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from backend.app.persistence.models import (Identity, IdentitySecret, IdentityVerification,
    OpenApiOperation, Resource, ResourceType, Target)


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=120)
    decision: Literal["ALLOW", "DENY", "UNKNOWN"]
    relation: Literal["ANY", "OWNER", "NON_OWNER", "SHARED"] = "ANY"
    operation_ids: list[int] = Field(default_factory=list)
    resource_type_id: int | None = None
    identity_ids: list[int] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)


class ResponseEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    denial_pointer: str | None = Field(default=None, pattern=r"^/")
    denial_value: str | None = None
    # A result identity and protected result fields are both required for BFLA.
    result_pointer: str | None = Field(default=None, pattern=r"^/")
    result_value: str | None = None
    protected_pointers: list[str] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def valid(self):
        if (self.denial_pointer is None) != (self.denial_value is None):
            raise ValueError("Denial pointer/value must be configured together")
        if any(not p.startswith("/") for p in self.protected_pointers):
            raise ValueError("Protected pointers must be JSON pointers")
        if self.result_pointer in self.protected_pointers:
            raise ValueError("Function result identity cannot be its sole protected evidence")
        return self


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: int
    kind: Literal["BOLA", "BFLA"]
    approved: bool = False
    evidence: ResponseEvidence | None = None
    resource_type_id: int | None = None

    @model_validator(mode="after")
    def mapping(self):
        if (self.kind == "BOLA") != (self.resource_type_id is not None):
            raise ValueError("BOLA requires one resource type; BFLA is function-level")
        return self


class Sharing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: int
    identity_ids: list[int]


class AuthorizationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: list[Rule] = Field(default_factory=list, max_length=1000)
    operations: list[Approval] = Field(default_factory=list, max_length=1000)
    sharing: list[Sharing] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def unique(self):
        for values in ([r.key for r in self.rules], [o.operation_id for o in self.operations],
                       [s.resource_id for s in self.sharing]):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate rule, ambiguous operation mapping or sharing definition")
        return self


def revision(config):
    payload = config.model_dump()
    # Optional execution evidence must not change revisions already persisted by
    # the original model/preview contract when no evidence was configured.
    for operation in payload["operations"]:
        if operation.get("evidence") is None:
            operation.pop("evidence", None)
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def configuration_rows(session, project_id):
    def rows(model):
        return list(session.scalars(select(model).where(model.project_id == project_id).order_by(model.id)))
    identities, operations, types = rows(Identity), rows(OpenApiOperation), rows(ResourceType)
    resources = list(session.scalars(select(Resource).where(Resource.resource_type_id.in_([t.id for t in types])).order_by(Resource.id)))
    return identities, operations, types, resources


def validate_references(config, identities, operations, types, resources):
    ids, ops, tids, rids = ({x.id for x in rows} for rows in (identities, operations, types, resources))
    for approval in config.operations:
        if approval.operation_id not in ops or (approval.resource_type_id is not None and approval.resource_type_id not in tids):
            raise ValueError("Operation/resource mapping must belong to project")
    for rule in config.rules:
        if not set(rule.identity_ids) <= ids or not set(rule.operation_ids) <= ops or (rule.resource_type_id is not None and rule.resource_type_id not in tids):
            raise ValueError("Rule references must belong to project")
    for share in config.sharing:
        if share.resource_id not in rids or not set(share.identity_ids) <= ids:
            raise ValueError("Sharing references must belong to project")


def decision(config, approval, actor, resource):
    shared = resource is not None and any(s.resource_id == resource.id and actor.id in s.identity_ids for s in config.sharing)
    owner = resource is not None and actor.id == resource.owner_identity_id
    matched = []
    for rule in config.rules:
        if rule.operation_ids and approval.operation_id not in rule.operation_ids:
            continue
        if rule.resource_type_id is not None and rule.resource_type_id != approval.resource_type_id:
            continue
        if rule.identity_ids and actor.id not in rule.identity_ids:
            continue
        if rule.roles and actor.role not in rule.roles:
            continue
        if rule.relation == "OWNER" and not owner:
            continue
        if rule.relation == "NON_OWNER" and (resource is None or owner):
            continue
        if rule.relation == "SHARED" and not shared:
            continue
        matched.append(rule)
    # Deny overrides every allow, including shared/owner/admin. Unknown never
    # becomes permission: a matching unresolved rule blocks an allow resolution.
    result = next((d for d in ("DENY", "UNKNOWN", "ALLOW") if any(r.decision == d for r in matched)), "UNKNOWN")
    return result, sorted(r.key for r in matched), shared


def preview(session, project_id, target, config):
    identities, operations, types, resources = configuration_rows(session, project_id)
    validate_references(config, identities, operations, types, resources)
    by_id = {x.id: x for x in identities}
    ops = {x.id: x for x in operations}
    secret_ids = set(session.scalars(select(IdentitySecret.identity_id).where(IdentitySecret.identity_id.in_(by_id))))
    latest = {}
    for check in session.scalars(select(IdentityVerification).where(IdentityVerification.target_id == target.id).order_by(IdentityVerification.id)):
        latest[check.identity_id] = check
    exclusions = []
    eligible = []
    for actor in identities:
        check = latest.get(actor.id)
        reason = ("MISSING_CREDENTIAL" if actor.id not in secret_ids else
                  "MISSING_PRINCIPAL_MAPPING" if not actor.principal_pointer or actor.expected_principal is None else
                  "IDENTITY_NOT_VERIFIED" if check is None or not check.authentication_passed or not check.principal_matched or check.execution_status != "COMPLETED_RESPONSE" else None)
        if reason:
            exclusions.append({"identity_id": actor.id, "reason": reason})
        else:
            eligible.append(actor)
    policy_revision = revision(config)
    cases, warnings = [], []
    for approval in sorted(config.operations, key=lambda a: a.operation_id):
        operation = ops[approval.operation_id]
        if not approval.approved or not operation.selected:
            warnings.append({"operation_id": operation.id, "reason": "OPERATION_NOT_APPROVED_OR_SELECTED"})
            continue
        objects = [None] if approval.kind == "BFLA" else [r for r in resources if r.resource_type_id == approval.resource_type_id]
        if not objects:
            warnings.append({"operation_id": operation.id, "reason": "NO_CONFIGURED_RESOURCES"})
        for resource in objects:
            problems = []
            if resource is not None:
                if resource.owner_identity_id not in by_id:
                    problems.append("UNKNOWN_OWNER")
                if not resource.external_id or set(re.findall(r"\{([^{}]+)\}", operation.path)) != {resource.path_parameter}:
                    problems.append("AMBIGUOUS_RESOURCE_MAPPING")
            elif "{" in operation.path:
                problems.append("UNRESOLVED_FUNCTION_PARAMETERS")
            decisions = {a.id: decision(config, approval, a, resource) for a in eligible}
            allowed = [a.id for a in eligible if decisions[a.id][0] == "ALLOW"]
            owner_id = resource.owner_identity_id if resource else None
            baseline = owner_id if owner_id in allowed else (min(allowed) if allowed else None)
            for actor in eligible:
                expected, rule_keys, shared = decisions[actor.id]
                reasons = list(problems)
                if expected == "UNKNOWN":
                    reasons.append("UNKNOWN_POLICY")
                if baseline is None:
                    reasons.append("MISSING_AUTHORIZED_BASELINE")
                if operation.method != "GET":
                    reasons.append("DISPOSABLE_WRITE_AUTHORIZATION_REQUIRED")
                elif approval.kind == "BFLA" and not (approval.evidence and
                        approval.evidence.result_pointer and approval.evidence.result_value is not None and
                        approval.evidence.protected_pointers):
                    reasons.append("FUNCTION_EXECUTION_EVIDENCE_REQUIRED")
                key = f"autoauth:v1:project:{project_id}:operation:{operation.id}:{approval.kind}:resource:{resource.id if resource else '-'}:actor:{actor.id}"
                owner = by_id.get(owner_id)
                relation = ("FUNCTION" if resource is None else "OWNER" if actor.id == owner_id else "SHARED" if shared else "CROSS_ROLE" if owner and actor.role != owner.role else "CROSS_IDENTITY")
                cases.append(dict(case_id=key, kind=approval.kind, operation_id=operation.id, method=operation.method,
                    path_template=operation.path, actor_identity_id=actor.id, actor_role=actor.role,
                    resource_id=resource.id if resource else None, owner_identity_id=owner_id,
                    relationship=relation, expected_decision=expected, matched_rule_keys=rule_keys,
                    policy_revision=policy_revision, baseline_identity_id=baseline,
                    baseline_kind="OWNER" if baseline is not None and baseline == owner_id else "AUTHORIZED_ACTOR" if baseline is not None else None,
                    owner_baseline_available=owner_id in allowed if resource else None,
                    execution_status="NOT_RUN", execution_eligible=not reasons, reasons=reasons))
    represented = {c["actor_identity_id"] for c in cases}
    for actor in eligible:
        if actor.id not in represented:
            exclusions.append({"identity_id": actor.id, "reason": "NO_VALID_APPROVED_OPERATION"})
    executable = [c for c in cases if c["execution_eligible"]]
    baselines = {(c["operation_id"], c["resource_id"], c["baseline_identity_id"]) for c in executable}
    verify = {c["actor_identity_id"] for c in executable} | {b[2] for b in baselines}
    budget = len(executable) + len(baselines) + len(verify)
    return dict(schema_version=1, policy_revision=policy_revision, cases=cases, exclusions=exclusions,
        warnings=warnings, identity_count=len(identities), actor_case_count=len(cases),
        executable_case_count=len(executable), identity_verifications=len(verify), authorized_baselines=len(baselines),
        planned_attempts=budget, request_limit=target.request_limit, within_request_limit=budget <= target.request_limit,
        execution_contract="EXPLICIT_SELECTED_CASES_V3_GET_ONLY")
