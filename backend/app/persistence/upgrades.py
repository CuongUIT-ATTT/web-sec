"""Additive SQLite upgrades that never rewrite historical authorization evidence."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy import Engine, inspect, text


T18_MIGRATION_ID = "20261106_t18_batch_execution_ledger"


class UpgradeError(RuntimeError):
    """Raised before an unsafe schema mutation would be attempted."""


@dataclass(frozen=True)
class DuplicateCaseKeyReport:
    """Opaque read-only diagnostic for historical non-null case-key duplicates."""

    column_state: str
    duplicate_groups: tuple[tuple[str, int], ...]

    @property
    def clean(self) -> bool:
        return not self.duplicate_groups

    def as_dict(self) -> dict[str, Any]:
        return {
            "column_state": self.column_state,
            "duplicate_groups": [
                {"run_hash": run_hash, "count": count}
                for run_hash, count in self.duplicate_groups
            ],
        }


def inspect_run_result_case_keys(engine: Engine) -> DuplicateCaseKeyReport:
    """Inspect legacy evidence without writing data or exposing case identifiers."""
    inspector = inspect(engine)
    if "run_results" not in inspector.get_table_names():
        return DuplicateCaseKeyReport("absent_table", ())
    columns = {column["name"]: column for column in inspector.get_columns("run_results")}
    case_key = columns.get("case_key")
    if case_key is None:
        return DuplicateCaseKeyReport("absent_column", ())
    column_state = "not_null" if not case_key.get("nullable", True) else "nullable"
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT run_id, COUNT(*) AS duplicate_count "
            "FROM run_results "
            "WHERE case_key IS NOT NULL "
            "GROUP BY run_id, case_key HAVING COUNT(*) > 1"
        )).all()
    groups = tuple(
        (sha256(f"run:{int(row.run_id)}".encode("utf-8")).hexdigest()[:16], int(row.duplicate_count))
        for row in rows
    )
    return DuplicateCaseKeyReport(column_state, groups)


def _table_columns(connection, table_name: str) -> set[str]:
    return {
        str(row.name)
        for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
    }


def upgrade_database(engine: Engine) -> DuplicateCaseKeyReport:
    """Apply the additive T18 ledger upgrade after a read-only duplicate preflight."""
    report = inspect_run_result_case_keys(engine)
    if not report.clean:
        raise UpgradeError("Historical non-null run-result case keys are duplicated; refusing additive upgrade.")

    with engine.connect() as connection:
        connection.execute(text("BEGIN IMMEDIATE"))
        try:
            existing_tables = set(inspect(connection).get_table_names())
            if "schema_migrations" not in existing_tables:
                connection.execute(text(
                    "CREATE TABLE schema_migrations ("
                    "migration_id VARCHAR(120) PRIMARY KEY NOT NULL, "
                    "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
                ))
            applied = connection.execute(
                text("SELECT 1 FROM schema_migrations WHERE migration_id = :migration_id"),
                {"migration_id": T18_MIGRATION_ID},
            ).scalar()
            if not applied:
                if "batch_case_claims" in existing_tables:
                    columns = _table_columns(connection, "batch_case_claims")
                    required = {"id", "run_id", "case_key", "payload_fingerprint", "run_result_id", "created_at", "updated_at"}
                    if not required.issubset(columns):
                        raise UpgradeError("Interrupted batch ledger upgrade has an incompatible table; no data was changed.")
                else:
                    connection.execute(text(
                        "CREATE TABLE batch_case_claims ("
                        "id INTEGER PRIMARY KEY, "
                        "run_id INTEGER NOT NULL REFERENCES runs(id), "
                        "case_key VARCHAR(256) NOT NULL, "
                        "payload_fingerprint VARCHAR(64) NOT NULL, "
                        "run_result_id INTEGER UNIQUE REFERENCES run_results(id), "
                        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                        "CONSTRAINT uq_batch_case_claim UNIQUE (run_id, case_key))"
                    ))
                if "run_execution_stats" in existing_tables:
                    columns = _table_columns(connection, "run_execution_stats")
                    required = {
                        "id", "run_id", "planned_attempts", "transport_attempts",
                        "completed_responses", "scope_blocked", "transport_errors", "cancelled_cases", "created_at", "updated_at",
                    }
                    if not required.issubset(columns):
                        raise UpgradeError("Interrupted execution-stats upgrade has an incompatible table; no data was changed.")
                else:
                    connection.execute(text(
                        "CREATE TABLE run_execution_stats ("
                        "id INTEGER PRIMARY KEY, "
                        "run_id INTEGER NOT NULL UNIQUE REFERENCES runs(id), "
                        "planned_attempts INTEGER NOT NULL DEFAULT 0, "
                        "transport_attempts INTEGER NOT NULL DEFAULT 0, "
                        "completed_responses INTEGER NOT NULL DEFAULT 0, "
                        "scope_blocked INTEGER NOT NULL DEFAULT 0, "
                        "transport_errors INTEGER NOT NULL DEFAULT 0, "
                        "cancelled_cases INTEGER NOT NULL DEFAULT 0, "
                        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
                        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
                    ))
                if report.column_state in {"nullable", "not_null"}:
                    connection.execute(text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_run_results_nonnull_case_key "
                        "ON run_results (run_id, case_key) WHERE case_key IS NOT NULL"
                    ))
                connection.execute(
                    text("INSERT INTO schema_migrations (migration_id) VALUES (:migration_id)"),
                    {"migration_id": T18_MIGRATION_ID},
                )
            connection.execute(text("COMMIT"))
        except Exception:
            connection.execute(text("ROLLBACK"))
            raise
    return report
