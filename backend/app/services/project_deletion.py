"""Transactional removal of project-owned configuration and stored evidence."""
from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.app.persistence.database import Base
from backend.app.persistence.models import Project, Run, ExternalLabJob


def delete_project(session: Session, project_id: int, confirmation_name: str) -> None:
    # Serialize against SQLite writers before checking workers or reading ownership.
    session.execute(text("BEGIN IMMEDIATE"))
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Không tìm thấy dự án.")
    if confirmation_name != project.name:
        raise HTTPException(422, "Nhập đúng tên dự án để xác nhận xóa.")
    for model, terminal in (
        (Run, ("COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED")),
        (ExternalLabJob, ("SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED")),
    ):
        if session.scalar(select(model.id).where(model.project_id == project_id, model.status.not_in(terminal)).limit(1)):
            raise HTTPException(409, "Không thể xóa dự án khi run hoặc lab job còn hoạt động.")
    # Build ownership through declared FKs, then delete children before parents.
    # This also covers revisions, comparison bundles and all run evidence tables.
    predicates = {Project.__table__: Project.__table__.c.id == project_id}
    for table in Base.metadata.sorted_tables:
        if table in predicates:
            continue
        parents = [column.in_(select(fk.column).where(predicates[fk.column.table]))
                   for column in table.columns for fk in column.foreign_keys
                   if fk.column.table in predicates]
        if parents:
            predicates[table] = or_(*parents)
    for table in reversed(Base.metadata.sorted_tables):
        if table in predicates:
            session.execute(delete(table).where(predicates[table]))
    session.commit()
