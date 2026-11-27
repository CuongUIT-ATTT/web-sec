"""Admin and CSRF protected, explicit synthetic project creation."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.persistence.models import Identity, Target
from backend.app.api.routes import get_session, verify_identity
from backend.app.core.auth import require_csrf
from backend.app.services.demo_seed import seed_demo

router = APIRouter(prefix="/api/demo", tags=["synthetic-demo"])


@router.post("/seed", dependencies=[Depends(require_csrf)])
async def load_demo(request: Request, session: Session = Depends(get_session)):
    try:
        project, created = seed_demo(session, request.app.state.settings)
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Dữ liệu mẫu bị trùng; dữ liệu hiện có được giữ nguyên.") from None
    except ValueError as error:
        session.rollback()
        raise HTTPException(409, str(error)) from error
    # Only the initial seed verifies fixture principals over real HTTP GET.
    # No matrix/run is queued; a failed check remains visible in Setup.
    if created:
        target = session.scalar(select(Target).where(Target.project_id == project.id))
        for actor in session.scalars(select(Identity).where(Identity.project_id == project.id)):
            await verify_identity(actor.id, target.id, request, None, session)
    return dict(project_id=project.id, created=created, synthetic=True)


@router.post("/ssh-seed", dependencies=[Depends(require_csrf)])
def load_ssh_demo(request: Request, session: Session = Depends(get_session)):
    from backend.app.persistence.models import Project
    from backend.app.services.ssh_seed import seed_ssh, SSH_NAME, SSH_DESCRIPTION
    try:
        # Serialize creation and preserve operator edits on repeated clicks.
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        project = session.scalar(select(Project).where(Project.name == SSH_NAME))
        if project is not None:
            if project.description != SSH_DESCRIPTION:
                raise ValueError("Tên dự án mẫu đã được dùng; dữ liệu hiện có được giữ nguyên.")
            project_id = project.id
            session.commit()
            return dict(project_id=project_id, created=False, synthetic=False)
        project, _ = seed_ssh(session, request.app.state.settings, transaction_started=True)
        project_id = project.id
        session.commit()
        return dict(project_id=project_id, created=True, synthetic=False)
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Dữ liệu mẫu bị trùng; dữ liệu hiện có được giữ nguyên.") from None
    except ValueError as error:
        session.rollback()
        raise HTTPException(409, str(error)) from error
