"""Generated private storage paths; temporary and immutable originals separated."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
from uuid import uuid4
from fastapi import HTTPException
from .config import ROOT


def directories(settings):
    root = settings.data_dir.resolve()
    if root in {ROOT, ROOT / "frontend"} or (ROOT / "frontend") in root.parents:
        raise ValueError("Storage cannot be a public/project root")
    for name in ("originals", "temporary"):
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("Symlink storage unsupported")
    return root


def original(settings, key):
    if not re.fullmatch(r"[0-9a-f]{32}\.(pdf|txt)", key):
        raise HTTPException(404, "Original file unavailable")
    root = directories(settings) / "originals"
    path = root / key
    if path.is_symlink() or path.resolve().parent != root.resolve():
        raise HTTPException(404, "Original file unavailable")
    return path


def filename_format(filename):
    if not filename or len(filename) > 180 or any(c in filename for c in '/\\:\x00\r\n'):
        raise HTTPException(422, "Use a simple PDF/TXT filename, without a path")
    extension = Path(filename).suffix.lower()[1:]
    if extension not in {"pdf", "txt"}:
        raise HTTPException(415, "Only digital PDF and UTF-8 TXT are supported")
    return extension


def parser_command(settings, path, format, output, progress=None, validate=False):
    command = [sys.executable, str(ROOT / "backend" / "parser_child.py"), str(path), format, str(output),
               "--max-pages", str(settings.max_pages), "--max-chars", str(settings.max_text_chars)]
    if validate:
        command.append("--validate")
    if progress:
        command.extend(["--progress", str(progress)])
    # No secrets inherited by the parsing child through environment variables.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GOV_")}
    return command, environment


def validate_file(settings, path, format):
    from .processes import spawn_owned
    output = directories(settings) / "temporary" / f"{uuid4().hex}.json"
    command, environment = parser_command(settings, path, format, output, validate=True)
    process = tree = None
    try:
        process,tree = spawn_owned(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process.wait(timeout=settings.parser_seconds)
        if process.returncode or not output.exists():
            raise HTTPException(422, "File parser failed")
        payload = json.loads(output.read_text("utf-8"))
        if "error" in payload:
            raise HTTPException(422, f"File rejected: {payload['error']}")
        return payload
    except subprocess.TimeoutExpired:
        raise HTTPException(422, "File parser exceeded its time limit") from None
    finally:
        if tree: tree.close()
        if process and process.poll() is None: process.wait(timeout=10)
        output.unlink(missing_ok=True)
        Path(str(output) + ".part").unlink(missing_ok=True)


def checksum_file(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()
