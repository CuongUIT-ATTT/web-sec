"""Authenticated serialized DTO ingress and project-scoped comparison reads."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.api.routes import get_session
from backend.app.core.auth import require_admin, require_csrf
from backend.app.persistence.models import Project, ComparisonBundle
from backend.app.comparison.validation import validate_dto, MAX_BUNDLE_BYTES
from backend.app.services.comparison_evidence import store_bundle, read_bundle

router = APIRouter(prefix='/api/projects/{project_id}/comparisons', tags=['comparison'])


def project(session, project_id):
    if session.get(Project, project_id) is None:
        raise HTTPException(404, 'Không tìm thấy dự án.')


@router.post('', status_code=201, dependencies=[Depends(require_csrf)])
async def ingest(project_id: int, request: Request, session: Session = Depends(get_session)):
    project(session, project_id)
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'Yêu cầu JSON.')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BUNDLE_BYTES:
            raise HTTPException(413, 'Comparison vượt giới hạn.')
    try:
        dto = validate_dto(bytes(raw))
        row = store_bundle(session, project_id, dto)
    except (ValueError, TypeError, KeyError, RecursionError):
        raise HTTPException(422, 'Comparison không hợp lệ.') from None
    return {'content_digest': row.content_digest, 'attestation_status': 'UNVERIFIED'}


@router.get('', dependencies=[Depends(require_admin)])
def inventory(project_id: int, offset: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    project(session, project_id)
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, 'Giới hạn không hợp lệ.')
    rows = session.scalars(select(ComparisonBundle).where(ComparisonBundle.project_id == project_id)
                          .order_by(ComparisonBundle.id).offset(offset).limit(limit))
    return [{'content_digest': r.content_digest, 'attestation_status': 'UNVERIFIED'} for r in rows]


@router.get('/{digest}', dependencies=[Depends(require_admin)])
def detail(project_id: int, digest: str, session: Session = Depends(get_session)):
    project(session, project_id)
    row = session.scalar(select(ComparisonBundle).where(ComparisonBundle.project_id == project_id,
                                                       ComparisonBundle.content_digest == digest))
    if row is None:
        raise HTTPException(404, 'Không tìm thấy comparison.')
    try:
        return read_bundle(row)
    except (ValueError, TypeError, KeyError, RecursionError):
        raise HTTPException(409, 'Comparison lưu trữ không hợp lệ.') from None
