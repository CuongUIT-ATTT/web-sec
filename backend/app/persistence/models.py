"""Durable configuration and run metadata without plaintext credentials or bodies."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.persistence.database import Base


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Project(Timestamped, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    targets: Mapped[list["Target"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Target(Timestamped, Base):
    __tablename__ = "targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(nullable=False, default=5.0)
    request_limit: Mapped[int] = mapped_column(nullable=False, default=100)
    verification_path: Mapped[str] = mapped_column(String(512), nullable=False, default="/me")
    project: Mapped[Project] = relationship(back_populates="targets")


class Identity(Timestamped, Base):
    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("project_id", "display_name", name="uq_identity_project_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str | None] = mapped_column(String(120))
    principal_pointer: Mapped[str | None] = mapped_column(String(512))
    expected_principal: Mapped[str | None] = mapped_column(String(512))
    secret: Mapped["IdentitySecret | None"] = relationship(back_populates="identity", cascade="all, delete-orphan", uselist=False)


class IdentitySecret(Timestamped, Base):
    __tablename__ = "identity_secrets"

    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    identity: Mapped[Identity] = relationship(back_populates="secret")


class IdentityVerification(Timestamped, Base):
    __tablename__ = "identity_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), nullable=False)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id"), nullable=False)
    authentication_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    principal_matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class OpenApiOperation(Timestamped, Base):
    __tablename__ = "openapi_operations"
    __table_args__ = (UniqueConstraint("project_id", "operation_key", name="uq_operation_project_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[str] = mapped_column(String(12), nullable=False, default="GET")
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ResourceType(Timestamped, Base):
    __tablename__ = "resource_types"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_resource_type_project_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id_pointer: Mapped[str] = mapped_column(String(512), nullable=False)
    restricted_pointers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class Resource(Timestamped, Base):
    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("resource_type_id", "external_id", name="uq_resource_type_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_type_id: Mapped[int] = mapped_column(ForeignKey("resource_types.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(240), nullable=False)
    owner_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), nullable=False)
    path_parameter: Mapped[str] = mapped_column(String(120), nullable=False)


class OperationResourceMapping(Timestamped, Base):
    """Explicit, operator-approved GET operation to resource-type execution scope."""

    __tablename__ = "operation_resource_mappings"
    __table_args__ = (UniqueConstraint("operation_id", "resource_type_id", name="uq_operation_resource_mapping"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    operation_id: Mapped[int] = mapped_column(ForeignKey("openapi_operations.id"), nullable=False)
    resource_type_id: Mapped[int] = mapped_column(ForeignKey("resource_types.id"), nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Policy(Timestamped, Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    operation_id: Mapped[int] = mapped_column(ForeignKey("openapi_operations.id"), nullable=False)
    resource_type_id: Mapped[int] = mapped_column(ForeignKey("resource_types.id"), nullable=False)
    identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"))
    role: Mapped[str | None] = mapped_column(String(120))
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"))
    decision: Mapped[str] = mapped_column(String(16), nullable=False)


class Run(Timestamped, Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class RunIdentitySecret(Timestamped, Base):
    __tablename__ = "run_identity_secrets"
    __table_args__ = (UniqueConstraint("run_id", "identity_id", name="uq_run_identity_secret"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False)


class RunExecutionStats(Timestamped, Base):
    """Durable numeric accounting for a batch run; contains no request or credential data."""

    __tablename__ = "run_execution_stats"
    __table_args__ = (UniqueConstraint("run_id", name="uq_run_execution_stats"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    planned_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transport_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_responses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scope_blocked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transport_errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BatchCaseClaim(Timestamped, Base):
    """Additive idempotency ledger for new batch result evidence."""

    __tablename__ = "batch_case_claims"
    __table_args__ = (UniqueConstraint("run_id", "case_key", name="uq_batch_case_claim"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    case_key: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    run_result_id: Mapped[int | None] = mapped_column(ForeignKey("run_results.id"), unique=True)


class Finding(Timestamped, Base):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("project_id", "fingerprint", name="uq_project_finding_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    conclusion: Mapped[str] = mapped_column(String(40), nullable=False)
    operation_method: Mapped[str] = mapped_column(String(12), nullable=False)
    operation_path: Mapped[str] = mapped_column(String(512), nullable=False)
    policy_id: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_type_id: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_pointer: Mapped[str] = mapped_column(String(512), nullable=False)
    restricted_pointers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class FindingReproduction(Timestamped, Base):
    __tablename__ = "finding_reproductions"
    __table_args__ = (UniqueConstraint("finding_id", "run_result_id", name="uq_finding_run_result"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), nullable=False)
    run_result_id: Mapped[int] = mapped_column(ForeignKey("run_results.id"), nullable=False)
    actor_identity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=False)


class RunResult(Timestamped, Base):
    __tablename__ = "run_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    # The additive BatchCaseClaim ledger, not this historical table, enforces batch uniqueness.
    case_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)
    authorization_conclusion: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    http_status: Mapped[int | None] = mapped_column(Integer)
    response_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
