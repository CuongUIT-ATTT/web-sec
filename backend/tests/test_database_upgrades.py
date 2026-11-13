from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from backend.app.persistence.database import create_session_factory
from backend.app.persistence.upgrades import T18_MIGRATION_ID, T19_MIGRATION_ID, UpgradeError, inspect_run_result_case_keys


def test_clean_upgrade_creates_additive_ledger_and_stats(tmp_path: Path) -> None:
    database_path = tmp_path / "clean.sqlite3"
    create_session_factory(database_path)
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.connect() as connection:
        tables = {row.name for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))}
        migrations = set(connection.execute(text("SELECT migration_id FROM schema_migrations")).scalars())
    assert {"batch_case_claims", "run_execution_stats", "external_lab_jobs", "bridge_nonces", "schema_migrations"}.issubset(tables)
    assert migrations == {T18_MIGRATION_ID, T19_MIGRATION_ID}


def test_duplicate_legacy_keys_block_before_schema_mutation(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE run_results (id INTEGER PRIMARY KEY, run_id INTEGER, case_key TEXT)"))
        connection.execute(text("INSERT INTO run_results (run_id, case_key) VALUES (1, 'private-key'), (1, 'private-key'), (2, NULL), (2, NULL)"))
    report = inspect_run_result_case_keys(engine)
    assert report.column_state == "nullable"
    assert report.clean is False
    assert "private-key" not in repr(report.as_dict())
    with pytest.raises(UpgradeError):
        create_session_factory(database_path)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM run_results")).scalar_one() == 4
        assert connection.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'")).scalar_one() == 0
