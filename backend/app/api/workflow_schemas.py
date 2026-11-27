"""DTOs for the configured read-only authorization workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OpenApiImport(BaseModel):
    document: dict = Field(description="OpenAPI JSON upload already decoded by the browser.")


class OperationView(BaseModel):
    id: int
    operation_key: str
    method: str
    path: str
    selected: bool


class OperationUpdate(BaseModel):
    selected: bool


class ResourceTypeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    resource_id_pointer: str = Field(min_length=2, max_length=512)
    restricted_pointers: list[str] = Field(min_length=1, max_length=20)


class ResourceTypeView(ResourceTypeCreate):
    id: int


class ResourceTypeUpdate(ResourceTypeCreate):
    pass


class ResourceCreate(BaseModel):
    external_id: str = Field(min_length=1, max_length=240)
    owner_identity_id: int
    path_parameter: str = Field(min_length=1, max_length=120)


class ResourceView(BaseModel):
    owner_identity_id: int
    path_parameter: str
    external_id: str = "[REDACTED]"
    resource_alias: str = ""
    id: int
    resource_type_id: int


class ResourceUpdate(ResourceCreate):
    external_id: str | None = Field(default=None, min_length=1, max_length=240)


class ResourceRequestPreview(BaseModel):
    operation_id: int
    method: Literal["GET"]
    path: str


class ResourceInspection(ResourceView):
    request_previews: list[ResourceRequestPreview]


class OperationResourceMappingCreate(BaseModel):
    operation_id: int
    resource_type_id: int
    selected: bool = True


class OperationResourceMappingUpdate(BaseModel):
    selected: bool


class OperationResourceMappingView(OperationResourceMappingCreate):
    id: int
    project_id: int


class BatchPlanTargetView(BaseModel):
    operation_id: int
    operation_path: str
    resource_type_id: int
    resource_type_name: str
    resource_count: int
    actor_case_count: int


class BatchMatrixView(BaseModel):
    identity_count: int
    concrete_target_count: int
    actor_case_count: int
    identity_verifications: int
    owner_baselines: int
    planned_attempts: int
    maximum_http_requests: int
    request_limit: int
    within_request_limit: bool
    targets: list[BatchPlanTargetView]
    cases: list[MatrixCaseView]


class ExecutionSummaryView(BaseModel):
    planned_attempts: int
    transport_attempts: int
    completed_responses: int
    scope_blocked: int
    transport_errors: int
    cancelled_cases: int


class BatchRunCreate(BaseModel):
    target_id: int


class PolicyCreate(BaseModel):
    operation_id: int
    resource_type_id: int
    decision: str = Field(pattern="^(ALLOW|DENY|UNKNOWN)$")
    identity_id: int | None = None
    role: str | None = Field(default=None, max_length=120)
    resource_id: int | None = None


class PolicyView(PolicyCreate):
    id: int
    version: int


class PolicyUpdate(PolicyCreate):
    pass


class MatrixCaseView(BaseModel):
    case_key: str
    control_type: str
    actor_alias: str
    actor_role: str | None
    owner_alias: str
    owner_role: str | None
    resource_alias: str
    ownership_category: str
    expected_decision: str
    method: str
    path_template: str
    actor_identity_id: int
    resource_id: int
    policy_status: str
    operation_id: int
    owner_identity_id: int
    resolved_decision: str | None = None
    policy_id: int | None = None
    policy_version: int | None = None
    warnings: list[str]


class RunCreate(BaseModel):
    target_id: int
    resource_id: int
    operation_id: int


class RunView(BaseModel):
    id: int
    project_id: int
    status: str
    snapshot: dict
    execution_summary: ExecutionSummaryView | None = None


class ProtectedFieldView(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    alias: str = Field(pattern=r"^protected-[1-9][0-9]*$")
    owner_present: bool
    actor_present: bool
    owner_type: Literal["str", "int", "float", "bool", "dict", "list", "NoneType"] | None
    actor_type: Literal["str", "int", "float", "bool", "dict", "list", "NoneType"] | None
    matches_owner: bool


class ResultEvidenceView(BaseModel):
    """Versioned summary only; unknown metadata keys never reach clients."""
    model_config = ConfigDict(strict=True, extra="ignore")
    schema_version: Literal[1]
    engine: Literal["web-evaluator-v1"]
    run_id: int = Field(gt=0)
    case_key: str = Field(min_length=1)
    resource_id: int = Field(gt=0)
    actor_identity_id: int = Field(gt=0)
    owner_identity_id: int = Field(gt=0)
    owner_control_valid: bool
    owner_http_status: int | None = Field(ge=100, le=599)
    owner_execution_status: Literal["COMPLETED_RESPONSE", "NETWORK_ERROR", "TIMEOUT", "SCOPE_BLOCKED", "REQUEST_LIMIT_REACHED", "BODY_TRUNCATED", "JSON_PARSE_ERROR", "CANCELLED", "INTERNAL_ERROR"]
    owner_body_truncated: bool
    owner_json_parse_error: bool
    owner_principal_matches: bool
    actor_principal_matches: bool
    owner_resource_matches: bool
    actor_resource_matches: bool
    owner_restricted_evidence_valid: bool
    restricted_fields_match_owner: bool
    policy_id: int | None = Field(gt=0)
    policy_version: int | None = Field(gt=0)
    policy_decision: Literal["ALLOW", "DENY", "UNKNOWN"] | None
    policy_resolution: Literal["RESOLVED", "NO_MATCH", "UNRESOLVED_CONFLICT"]


class ResultEvidenceV2View(ResultEvidenceView):
    schema_version: Literal[2]
    actor_role: str | None = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
    owner_role: str | None = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
    ownership: Literal["self", "same-role-other", "cross-role", "unknown"]
    protected_fields: list[ProtectedFieldView]


class ResultMetadataView(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    body_length: int | None = Field(default=None, ge=0)
    body_truncated: bool | None = None
    json_parse_error: bool | None = None
    evidence: ResultEvidenceView | ResultEvidenceV2View | None = None


class RunResultView(BaseModel):
    case_key: str | None
    execution_status: str
    authorization_conclusion: str
    reason_codes: list[str]
    http_status: int | None
    response_metadata: ResultMetadataView


BatchMatrixView.model_rebuild()


class ComparisonMethodView(BaseModel):
    method: Literal["MANUAL", "T18", "ZAP"]
    execution_status: str
    observation: RunResultView | None = None
    provenance: str = "UNAVAILABLE"
    artifact: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    timing_status: Literal["TIMING_NOT_AVAILABLE"] = "TIMING_NOT_AVAILABLE"


class ComparisonCaseView(BaseModel):
    run_id: int
    case_key: str | None
    methods: list[ComparisonMethodView]


class ComparisonView(BaseModel):
    run_id: int
    cases: list[ComparisonCaseView]
