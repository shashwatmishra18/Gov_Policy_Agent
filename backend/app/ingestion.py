"""Durable single-document jobs with PostgreSQL leases and fenced result commits."""
from datetime import timedelta
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from .auth import now
from .document_models import Chunk, Document, DocumentVersion, ExtractedPage, IngestionJob
from .extraction import chunks, PROFILE, REVISION
from .storage import checksum_file, directories, original, parser_command
from .processes import spawn_owned


def claim(engine, settings):
    with Session(engine, expire_on_commit=False) as db:
        candidates = (select(IngestionJob).join(DocumentVersion).join(Document)
                      .where(Document.archived_at.is_(None),
                             (IngestionJob.state == "queued") | ((IngestionJob.state == "processing") & (IngestionJob.lease_until < now())))
                      .order_by(IngestionJob.created_at).with_for_update(of=IngestionJob, skip_locked=True).limit(1))
        job = db.scalar(candidates)
        if job is None:
            return None
        if job.attempts >= 3:
            job.state, job.error_code, job.finished_at = "failed", "attempt_limit_worker_interrupted", now()
            job.lease_owner, job.lease_until = None, None
            db.commit()
            return None
        job.attempts += 1
        job.state, job.error_code, job.progress = "processing", None, 0
        job.processed_pages, job.total_pages = 0, 0
        job.lease_owner = uuid4()
        job.heartbeat_at, job.lease_until = now(), now() + timedelta(seconds=settings.job_lease_seconds)
        job.finished_at = None
        version = db.get(DocumentVersion, job.version_id)
        result = (job.id, job.lease_owner, version.storage_key, version.format, version.checksum)
        db.commit()
        return result


def owned(db, job_id, token):
    return db.scalar(select(IngestionJob).where(IngestionJob.id == job_id, IngestionJob.state == "processing",
                     IngestionJob.lease_owner == token, IngestionJob.lease_until > now()).with_for_update())


def heartbeat(engine, settings, job_id, token, progress=None):
    with Session(engine) as db:
        job = owned(db, job_id, token)
        if job is None:
            return False
        job.heartbeat_at, job.lease_until = now(), now() + timedelta(seconds=settings.job_lease_seconds)
        if progress and progress["total"] > 0:
            job.processed_pages, job.total_pages = progress["processed"], progress["total"]
            job.progress = min(95, int(progress["processed"] * 95 / progress["total"]))
        db.commit()
        return True


def finish(engine, job_id, token, result):
    with Session(engine) as db:
        job = owned(db, job_id, token)
        if job is None:
            return False  # A restarted worker owns it; stale child cannot publish.
        if "error" in result:
            job.state, job.error_code = "failed", result["error"]
        else:
            version = db.get(DocumentVersion, job.version_id)
            if db.scalar(select(ExtractedPage.id).where(ExtractedPage.version_id == version.id).limit(1)):
                job.state,job.error_code='failed','existing_extraction_requires_revision'
                job.lease_owner=job.lease_until=None;job.finished_at=now();db.commit();return True
            # Derived results replaced coherently in one transaction, never incrementally published.
            db.execute(delete(Chunk).where(Chunk.version_id == version.id))
            db.execute(delete(ExtractedPage).where(ExtractedPage.version_id == version.id))
            chunk_number = 0
            digital = 0
            for page in result["pages"]:
                page_id = uuid4()
                db.add(ExtractedPage(id=page_id, version_id=version.id, **page))
                db.flush()
                if "needs_ocr" not in page["quality_flags"]:
                    digital += 1
                for chunk in chunks(page["text"]):
                    chunk_number += 1
                    db.add(Chunk(version_id=version.id, page_id=page_id, ordinal=chunk_number, **chunk))
            page_count = len(result["pages"])
            job.state = "completed" if digital == page_count else "needs_ocr" if digital == 0 else "partial"
            job.total_pages = job.processed_pages = page_count
            job.progress = 100
            version.extraction_revision = REVISION if version.format == "pdf" else "utf8-exact-v1"
            version.chunk_profile = PROFILE
        job.lease_owner, job.lease_until, job.finished_at = None, None, now()
        db.commit()
        return True


def process_claim(engine, settings, claimed):
    job_id, token, key, format, expected_checksum = claimed
    temporary = directories(settings) / "temporary"
    output, progress_path = temporary / f"{token.hex}.json", temporary / f"{token.hex}.progress"
    process = tree = None
    try:
        path = original(settings, key)
        if not path.is_file() or checksum_file(path) != expected_checksum:
            return finish(engine, job_id, token, {"error": "original_missing_or_changed"})
        command, environment = parser_command(settings, path, format, output, progress_path)
        process,tree = spawn_owned(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + settings.parser_seconds
        while process.poll() is None:
            if time.monotonic() > deadline:
                process.kill(); process.wait()
                return finish(engine, job_id, token, {"error": "parser_timeout"})
            progress = None
            if progress_path.exists():
                try:
                    progress = json.loads(progress_path.read_text("utf-8"))
                except (OSError, ValueError):
                    pass
            if not heartbeat(engine, settings, job_id, token, progress):
                process.kill(); process.wait()
                return False
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        if process.returncode or not output.exists() or output.stat().st_size > 32 * 1024 * 1024:
            return finish(engine, job_id, token, {"error": "parser_failed"})
        return finish(engine, job_id, token, json.loads(output.read_text("utf-8")))
    except Exception:
        # No text, path, SQL parameters or secret exception strings logged.
        return finish(engine, job_id, token, {"error": "processing_failed"})
    finally:
        if tree: tree.close()
        if process is not None and process.poll() is None:
            process.kill(); process.wait()
        for path in (output, progress_path, Path(str(output) + ".part"), Path(str(progress_path) + ".part")):
            path.unlink(missing_ok=True)


def run_once(engine, settings):
    claimed = claim(engine, settings)
    if claimed is None:
        return False
    process_claim(engine, settings, claimed)
    return True


def reconcile(engine, settings):
    """Explicit cleanup: generated files only, no symlinks or traversal; grace periods."""
    import re
    import shutil
    root = directories(settings)
    removed = 0
    with Session(engine) as db:
        known = set(db.scalars(select(DocumentVersion.storage_key)))
    for directory, minimum_age in [(root / "temporary", 3600), (root / "originals", 86400)]:
        for path in directory.iterdir():
            if (directory.name=='temporary' and path.is_dir() and not path.is_symlink()
                and re.fullmatch(r'ocr-[0-9a-f]{32}',path.name) and path.resolve().parent==directory.resolve()
                and time.time()-path.stat().st_mtime>3600):
                shutil.rmtree(path);removed+=1;continue
            if path.is_symlink() or not path.is_file() or not re.fullmatch(r"[0-9a-f]{32}\.(upload|json|progress|png|pdf|txt)(\.part)?", path.name):
                continue
            if directory.name == "originals" and path.name in known:
                continue
            if time.time() - path.stat().st_mtime > minimum_age:
                path.unlink(); removed += 1
    return removed
