"""DTOs for the configured read-only authorization workflow."""

from __future__ import annotations

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


class ResourceView(ResourceCreate):
    id: int
    resource_type_id: int


class ResourceUpdate(ResourceCreate):
    pass


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
    actor_identity_id: int
    resource_id: int
    policy_status: str
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
