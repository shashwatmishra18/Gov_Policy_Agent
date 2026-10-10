"""Authenticated facade; ordinary API never loads/downloads embedding models."""
from datetime import date
import hashlib
import hmac
from typing import Literal
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import admin_user, current_user, csrf, now, throttle
from .database import get_db
from .document_models import DocumentVersion
from .documents import require_version, page_text
from .eligibility import eligibility
from .index_models import EligibilityReview, IndexGeneration, IndexPassage, IndexState
from .models import User
from .vector_index import queue, status

router = APIRouter(tags=['retrieval'])


def internal_key(settings):
    return hmac.new(settings.jwt_secret.get_secret_value().encode(), b'part4-index-runtime', hashlib.sha256).hexdigest()


class SearchInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=2, max_length=2000)
    count: int = Field(default=5, ge=1, le=10)
    scheme: str | None = Field(default=None, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    document_type: str | None = Field(default=None, max_length=80)
    published_after: date | None = None
    published_before: date | None = None
    unknown_dates: Literal['exclude', 'include'] = 'exclude'

    @model_validator(mode='after')
    def dates(self):
        if not self.question.strip(): raise ValueError('empty_question')
        if self.published_after and self.published_before and self.published_after > self.published_before:
            raise ValueError('date_order')
        return self


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['verified', 'rejected']
    reuse_status: Literal['permission_recorded', 'local_reference_only', 'not_assessed']
    applicability: Literal['historical', 'unknown', 'current_verified']
    reason: str = Field(min_length=20, max_length=2000)
    evidence_url: HttpUrl
    scope: str = Field(min_length=20, max_length=2000)


@router.post('/admin/documents/versions/{version_id}/reviews', dependencies=[Depends(csrf)])
def review(version_id: UUID, body: ReviewInput, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    version = db.scalar(select(DocumentVersion).where(DocumentVersion.id == version_id).with_for_update())
    if not version: raise HTTPException(404, 'Version not found')
    if body.evidence_url.username or body.evidence_url.password or len(str(body.evidence_url)) > 1500:
        raise HTTPException(422, 'Evidence URL must have no credentials and fit 1500 characters')
    record = EligibilityReview(version_id=version.id, reviewer_id=user.id,
        **body.model_dump(exclude={'evidence_url'}), evidence_url=str(body.evidence_url))
    db.add(record); db.commit()
    return {'review_id': record.id, **eligibility(db, version)}


@router.get('/admin/documents/versions/{version_id}/reviews')
def reviews(version_id: UUID, page: int = Query(default=1, ge=1), user: User = Depends(admin_user), db: Session = Depends(get_db)):
    require_version(db, version_id)
    rows = db.scalars(select(EligibilityReview).where(EligibilityReview.version_id == version_id)
        .order_by(EligibilityReview.created_at.desc()).offset((page-1)*20).limit(20))
    return {'items': [{k: getattr(r,k) for k in ('id','decision','reuse_status','applicability','reason','evidence_url','scope','created_at')} for r in rows]}


@router.get('/search/status')
def search_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return status(db)


@router.post('/admin/index/rebuild', dependencies=[Depends(csrf)])
def rebuild(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    job = queue(db)
    return {'generation': str(job.id), 'state': job.state}


@router.post('/admin/index/{generation_id}/retry', dependencies=[Depends(csrf)])
def retry(generation_id: UUID, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    job = db.scalar(select(IndexGeneration).where(IndexGeneration.id == generation_id).with_for_update())
    if not job or job.state != 'failed' or job.attempts >= 3:
        raise HTTPException(409, 'Only failed indexing jobs below three attempts can retry')
    job.state, job.error_code = 'queued', None
    db.commit(); return {'state': job.state}


@router.post('/search', dependencies=[Depends(csrf)])
def search(body: SearchInput, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    throttle(db, request, str(user.id), 'search')
    try:
        result = httpx.post(request.app.state.settings.index_url+'/query', json=body.model_dump(mode='json'),
            headers={'X-Index-Key': internal_key(request.app.state.settings)}, timeout=20, trust_env=False)
        if result.status_code == 422: raise HTTPException(422, 'Question exceeds tokenizer limits; shorten it')
        if result.status_code != 200: raise HTTPException(503, 'Index service busy or unavailable')
        return result.json()
    except httpx.HTTPError:
        raise HTTPException(503, 'Index service unavailable; prepare model and start index service') from None


@router.get('/search/versions/{version_id}/pages/{ordinal}')
def inspect_page(version_id: UUID, ordinal: int, offset: int = Query(default=0, ge=0),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    version = require_version(db, version_id)
    pointer = db.get(IndexState, 1)
    job = db.get(IndexGeneration, pointer.active_id) if pointer and pointer.active_id else None
    snapshot = next((v for v in job.versions if v['id'] == str(version.id)), None) if job and job.state == 'ready' else None
    e = eligibility(db, version,snapshot.get('extraction_revision_id') if snapshot else None)
    if not e['eligible'] or not snapshot or e['review_id'] != snapshot['review_id']:
        raise HTTPException(403, 'Source is not in the active reviewed eligible generation')
    from .extraction_artifacts import pages_for
    artifact=next((p for original,p in pages_for(db,version_id,snapshot.get('extraction_revision_id')) if original.ordinal==ordinal),None)
    return page_text(version_id, ordinal, offset, db,artifact.id if artifact and snapshot.get('extraction_revision_id') else None)
