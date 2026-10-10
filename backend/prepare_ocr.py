"""Explicit official pinned language download; runtime never downloads."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
from app.config import Settings
from app.ocr import PACK_HASHES

REVISION = '87416418657359cb625c412a48b6e1d6d41c29bd'


def detect():
    candidates = [shutil.which('tesseract'),
        str(Path(os.environ.get('LOCALAPPDATA', ''))/'Programs/Tesseract-OCR/tesseract.exe'),
        r'C:\Program Files\Tesseract-OCR\tesseract.exe']
    if os.name != 'nt':
        if candidates[0]: return Path(candidates[0]).resolve()
        raise RuntimeError('Pinned Linux Tesseract 5.4.0 required')
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for key in ('SOFTWARE\\Tesseract-OCR','SOFTWARE\\WOW6432Node\\Tesseract-OCR'):
            try:
                with winreg.OpenKey(hive,key) as entry:
                    folder=winreg.QueryValueEx(entry,'Path')[0]
                    candidates.append(str(Path(folder)/'tesseract.exe'))
            except OSError:pass
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise RuntimeError('Tesseract missing: install the trusted UB-Mannheim Windows build')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--packs-source',type=Path);args=parser.parse_args()
    exe = detect()
    version = subprocess.check_output([str(exe), '--version'], timeout=10).decode().splitlines()[0]
    expected='tesseract v5.4.0.20240606' if os.name=='nt' else 'tesseract 5.4.0'
    if version!=expected:raise RuntimeError('Pinned platform-specific Tesseract engine required')
    root = Settings().data_dir.parent/'ocr'
    root.mkdir(parents=True, exist_ok=True)
    packs = {}
    for language in ('eng', 'hin'):
        url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{REVISION}/{language}.traineddata'
        target = root/f'{language}.traineddata'
        if args.packs_source:
            source=args.packs_source/f'{language}.traineddata'
            if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=PACK_HASHES[language]:raise RuntimeError('Reused language pack checksum mismatch')
            if source.resolve()!=target.resolve():shutil.copyfile(source,target)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=PACK_HASHES[language]:
            temporary = target.with_suffix('.download')
            urllib.request.urlretrieve(url, temporary)
            if hashlib.sha256(temporary.read_bytes()).hexdigest()!=PACK_HASHES[language]:
                temporary.unlink();raise RuntimeError('Official pinned language data checksum mismatch')
            temporary.replace(target)
        packs[language] = {'revision': REVISION, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'source': url}
    manifest = {'executable': str(exe), 'version': version,
        'executable_sha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'packs': packs,
        'license': 'Apache-2.0', 'preprocessing_revision': 'gray-pdf-rotation-v1', 'oem': 1, 'psm': 3}
    (root/'prepared.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(version)
    print(subprocess.check_output([str(exe), '--tessdata-dir', str(root), '--list-langs'], timeout=10).decode())
    print(json.dumps(packs, indent=2))
