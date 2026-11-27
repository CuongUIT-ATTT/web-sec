"""Immutable project-scoped comparison persistence. No lab or artifact resolution."""
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.app.persistence.models import ComparisonBundle
from backend.app.comparison.validation import validate_dto


def store_bundle(session, project_id, dto):
    canonical = json.dumps(dto, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    digest = dto['content_digest']
    query = select(ComparisonBundle).where(ComparisonBundle.project_id == project_id,
                                           ComparisonBundle.content_digest == digest)
    existing = session.scalar(query)
    if existing is None:
        existing = ComparisonBundle(project_id=project_id, content_digest=digest, canonical_json=canonical)
        session.add(existing)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(query)
            if existing is None:
                raise ValueError('Storage conflict') from None
    if existing.canonical_json != canonical:
        raise ValueError('Storage conflict')
    return existing


def read_bundle(row):
    dto = validate_dto(row.canonical_json.encode('ascii'))
    if dto['content_digest'] != row.content_digest:
        raise ValueError('Storage integrity failure')
    return dto
