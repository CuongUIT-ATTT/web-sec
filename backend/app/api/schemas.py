"""Public API DTOs; credentials are accepted write-only and never echoed."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=4096, repr=False)


class LoginResponse(BaseModel):
    csrf_token: str


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class ProjectView(BaseModel):
    id: int
    name: str
    description: str


class ProjectUpdate(ProjectCreate):
    pass


class TargetCreate(BaseModel):
    base_url: str = Field(min_length=1, max_length=512)
    timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    request_limit: int = Field(default=100, ge=1, le=1000)
    verification_path: str = Field(default="/me", min_length=1, max_length=512)


class TargetView(BaseModel):
    id: int
    project_id: int
    base_url: str
    timeout_seconds: float
    request_limit: int
    verification_path: str


class TargetUpdate(TargetCreate):
    pass


class IdentityCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    principal_pointer: str | None = Field(default=None, max_length=512)
    expected_principal: str | None = Field(default=None, max_length=512)
    bearer_token: str = Field(min_length=1, max_length=4096, repr=False)


class IdentityView(BaseModel):
    id: int
    display_name: str
    role: str | None
    principal_pointer: str | None
    expected_principal: str | None
    has_secret: bool


class IdentityUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    display_name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    principal_pointer: str | None = Field(default=None, max_length=512)
    expected_principal: str | None = Field(default=None, max_length=512)
    bearer_token: str | None = Field(default=None, min_length=1, max_length=4096, repr=False)


class TargetConnectionView(BaseModel):
    execution_status: str
    http_status: int | None
    reason_codes: list[str]


class IdentityVerificationView(BaseModel):
    authentication_passed: bool
    principal_matched: bool
    principal_confirmed: bool
    execution_status: str
    reason_codes: list[str]


class ErrorDetail(BaseModel):
    detail: str
