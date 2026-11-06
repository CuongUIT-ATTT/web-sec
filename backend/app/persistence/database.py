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
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
