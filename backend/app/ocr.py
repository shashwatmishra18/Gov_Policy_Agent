"""Fenced OCR revisions, bounded child ownership and append-only page review."""
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import now
from .config import ROOT
from .document_models import Document, DocumentVersion, ExtractedPage, IngestionJob
from .extraction import paragraphs
from .extraction_artifacts import pages_for, accepted
from .ocr_models import ExtractionRevision, ExtractionPage, ExtractionState
from .processes import spawn_owned
from .storage import directories, original, checksum_file

PACK_HASHES = {'eng':'7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
    'hin':'4c73ffc59d497c186b19d1e90f5d721d678ea6b2e277b719bee4e2af12271825'}


def prepared(settings):
    root = settings.data_dir.parent/'ocr'
    manifest = json.loads((root/'prepared.json').read_text('utf-8'))
    exe = Path(manifest['executable'])
    if not exe.is_absolute() or checksum_file(exe) != manifest['executable_sha256']: raise ValueError('ocr_engine_changed')
    expected = 'tesseract v5.4.0.20240606' if os.name=='nt' else 'tesseract 5.4.0'
    if manifest['version'] != expected: raise ValueError('ocr_engine_version')
    for language, digest in PACK_HASHES.items():
        if checksum_file(root/f'{language}.traineddata') != digest or manifest['packs'][language]['sha256'] != digest:
            raise ValueError('ocr_language_pack_changed')
    return root, manifest


def queue(db, settings, version_id, user_id):
    version = db.get(DocumentVersion, version_id, with_for_update=True)
    if not version or version.format != 'pdf': raise ValueError('ocr_pdf_required')
    document = db.get(Document, version.document_id)
    if document.archived_at: raise ValueError('source_archived')
    job = db.scalar(select(IngestionJob).where(IngestionJob.version_id == version.id))
    if not job or job.state not in ('partial','needs_ocr','completed'): raise ValueError('initial_extraction_required')
    pending = db.scalar(select(ExtractionRevision).where(ExtractionRevision.version_id == version.id,
        ExtractionRevision.state.in_(['queued','processing','pending_review'])))
    if pending: return pending
    pages = list(db.scalars(select(ExtractedPage).where(ExtractedPage.version_id == version.id)))
    if not any('needs_ocr' in p.quality_flags for p in pages): raise ValueError('no_ocr_pending_pages')
    _, manifest = prepared(settings)
    spec = {k:v for k,v in manifest.items() if k != 'executable'}
    spec.update(dpi=settings.ocr_dpi,max_pixels=settings.ocr_max_pixels,page_seconds=settings.ocr_page_seconds,
        original_sha256=version.checksum,quality_policy='manual-all-ocr-v1')
    revision = ExtractionRevision(version_id=version.id,creator_id=user_id,spec=spec,total=len(pages))
    db.add(revision);db.commit()
    return revision


def refresh_state(db, revision):
    if revision.state in ('queued','processing','cancelled','failed'): return
    pages = pages_for(db, revision.version_id, revision.id)
    if len(pages) == revision.total and all(accepted(db,p) for _,p in pages):
        revision.state = 'completed'
        state = db.get(ExtractionState,revision.version_id)
        if not state: db.add(ExtractionState(version_id=revision.version_id,ready_id=revision.id))
        else: state.ready_id = revision.id
    else: revision.state = 'pending_review' if all(p.method != 'failed' and 'low_quality' not in p.quality_flags for _,p in pages) else 'partial'


def owned(db, revision_id, token):
    revision = db.scalar(select(ExtractionRevision).where(ExtractionRevision.id == revision_id,
        ExtractionRevision.state == 'processing',ExtractionRevision.lease_owner == token,
        ExtractionRevision.lease_until > now()).with_for_update())
    if revision:
        version = db.get(DocumentVersion,revision.version_id)
        if db.get(Document,version.document_id).archived_at: return None
    return revision


def heartbeat(engine, revision_id, token):
    with Session(engine) as db:
        revision = owned(db,revision_id,token)
        if not revision: return False
        revision.lease_until = now()+timedelta(seconds=90);db.commit();return True


def claim(engine):
    with Session(engine,expire_on_commit=False) as db:
        revision = db.scalar(select(ExtractionRevision).join(DocumentVersion).join(Document)
            .where(Document.archived_at.is_(None),(ExtractionRevision.state == 'queued') |
                ((ExtractionRevision.state == 'processing') & (ExtractionRevision.lease_until < now())))
            .order_by(ExtractionRevision.created_at).with_for_update(of=ExtractionRevision,skip_locked=True).limit(1))
        if not revision: return None
        if revision.attempts >= 3:
            revision.state,revision.error_code = 'failed','attempt_limit';db.commit();return None
        revision.state,revision.lease_owner = 'processing',uuid4()
        revision.attempts += 1;revision.error_code = None
        revision.lease_until = now()+timedelta(seconds=90);db.commit()
        return revision.id,revision.lease_owner


def run_page(settings, request, beat):
    root = directories(settings)/'temporary'
    work = root/('ocr-'+uuid4().hex)
    work.mkdir()
    process = tree = None
    try:
        request_file = work/'request.json'
        request_file.write_text(json.dumps(request),encoding='utf-8')
        environment = {k:v for k,v in os.environ.items() if not k.startswith('GOV_')}
        process,tree = spawn_owned([sys.executable,str(ROOT/'backend/ocr_child.py'),str(request_file)],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=environment)
        process.stdin.write(b'1');process.stdin.flush();process.stdin.close()
        deadline = time.monotonic()+request['seconds']
        while process.poll() is None:
            if time.monotonic()>deadline: return {'error':'ocr_timeout'}
            if not beat(): return {'error':'ocr_lease_lost'}
            try:process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:pass
        output = work/'output.json'
        if process.returncode or not output.is_file() or output.stat().st_size>8*1024*1024: return {'error':'ocr_failed'}
        return json.loads(output.read_text('utf-8'))
    finally:
        if tree: tree.close()
        if process and process.poll() is None:process.kill();process.wait(timeout=10)
        # Only the freshly generated private directory, never an original or arbitrary client path.
        if work.resolve().parent != root.resolve() or work.is_symlink(): raise ValueError('ocr_cleanup_path')
        shutil.rmtree(work)


def run_once(engine, settings):
    claimed = claim(engine)
    if not claimed: return False
    revision_id,token = claimed
    try:
        packs,manifest = prepared(settings)
        with Session(engine) as db:
            revision = owned(db,revision_id,token)
            if not revision:return True
            version = db.get(DocumentVersion,revision.version_id)
            path = original(settings,version.storage_key)
            if checksum_file(path) != revision.spec['original_sha256']: raise ValueError('original_missing_or_changed')
            if {k:v for k,v in manifest.items() if k!='executable'} != {k:v for k,v in revision.spec.items()
                    if k not in ('dpi','max_pixels','page_seconds','original_sha256','quality_policy')}:
                raise ValueError('ocr_preparation_changed')
            spec,attempt = revision.spec,revision.attempts
            pages = list(db.scalars(select(ExtractedPage).where(ExtractedPage.version_id==version.id).order_by(ExtractedPage.ordinal)))
        for page in pages:
            with Session(engine) as db:
                revision = owned(db,revision_id,token)
                if not revision:return True
                latest = db.scalar(select(ExtractionPage).where(ExtractionPage.revision_id==revision_id,
                    ExtractionPage.page_id==page.id).order_by(ExtractionPage.attempt.desc()).limit(1))
                # Restart keeps already published digital/legible OCR artifacts, including pending review.
                if latest and latest.method!='failed' and 'low_quality' not in latest.quality_flags:continue
            digital = 'needs_ocr' not in page.quality_flags
            payload = {'text':page.text,'quality_flags':page.quality_flags,'signals':{},'boxes':[]} if digital else run_page(settings,
                {'path':str(path),'ordinal':page.pdf_page_number,'manifest':manifest,'packs':str(packs),
                    'dpi':spec['dpi'],'max_pixels':spec['max_pixels'],'seconds':spec['page_seconds']},
                lambda:heartbeat(engine,revision_id,token))
            with Session(engine) as db:
                revision = owned(db,revision_id,token)
                if not revision:return True
                if db.scalar(select(ExtractionPage.id).where(ExtractionPage.revision_id==revision_id,
                    ExtractionPage.page_id==page.id,ExtractionPage.attempt==(0 if digital else attempt))):continue
                text_value = payload.get('text','')
                existing = pages_for(db,revision.version_id,revision_id)
                if sum(len(p.text) for original,p in existing if original.id!=page.id)+len(text_value)>settings.max_text_chars:raise ValueError('ocr_document_text_limit')
                db.add(ExtractionPage(revision_id=revision_id,page_id=page.id,attempt=0 if digital else attempt,
                    text=text_value,paragraphs=paragraphs(text_value),method='digital' if digital else 'failed' if 'error' in payload else 'ocr',
                    quality_flags=payload.get('quality_flags',[payload.get('error','ocr_failed')]),
                    signals=payload.get('signals',{}),boxes=payload.get('boxes',[])))
                db.flush();revision.processed=len(pages_for(db,revision.version_id,revision_id));db.commit()
        with Session(engine) as db:
            revision = owned(db,revision_id,token)
            if revision:
                revision.state='pending_review';revision.lease_owner=revision.lease_until=None
                refresh_state(db,revision);db.commit()
    except Exception as exc:
        with Session(engine) as db:
            revision = owned(db,revision_id,token)
            if revision:
                revision.state='failed';revision.error_code = str(exc) if str(exc) in ('original_missing_or_changed','ocr_preparation_changed','ocr_document_text_limit') else 'ocr_processing_failed'
                revision.lease_owner=revision.lease_until=None;db.commit()
    return True
