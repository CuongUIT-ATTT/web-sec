"""SQLite setup for the single-process authorization-testing MVP."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base type for durable, non-secret metadata."""


def create_sqlite_engine(database_path: Path):
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )


def create_session_factory(database_path: Path) -> sessionmaker[Session]:
    """Create missing tables and apply additive, evidence-preserving upgrades."""
    engine = create_sqlite_engine(database_path)
    # Import models before metadata creation while keeping this module import-safe.
    from backend.app.persistence import models  # noqa: F401
    from backend.app.persistence.upgrades import inspect_run_result_case_keys, upgrade_database

    # The inspection happens before any DDL; it never mutates legacy evidence.
    report = inspect_run_result_case_keys(engine)
    if not report.clean:
        from backend.app.persistence.upgrades import UpgradeError
        raise UpgradeError("Historical non-null run-result case keys are duplicated; refusing schema mutation.")
    Base.metadata.create_all(engine)
    upgrade_database(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
