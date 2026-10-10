"""Offline private database/originals bundle; restore only into an empty package installation."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tarfile

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def sql(statement):
    return subprocess.run(['psql','-X','-At','-v','ON_ERROR_STOP=1','-c',statement],env=env,text=True,capture_output=True,check=True).stdout.strip()

def main():
    action=sys.argv[1] if len(sys.argv)==2 else ''
    if action not in ('backup','restore'):raise ValueError('Choose backup or restore')
    # Fixed private Docker service address, never an arbitrary native target.
    if any(os.environ.get(k)!=v for k,v in {'PGHOST':'postgres','PGDATABASE':'gov_package','PGUSER':'gov_app'}.items()):raise ValueError('Package database required')
    global env
    env=os.environ.copy();env['PGPASSWORD']=Path('/run/secrets/app_password').read_text().strip()
    if sql("SELECT count(*) FROM pg_stat_activity WHERE usename=current_user AND pid<>pg_backend_pid()")!='0':raise ValueError('Stop all package application services before backup/restore')
    root=Path('/state/data/originals');bundle=Path('/backup/bundle')
    pins={'generation':json.loads(Path('/model-pins.json').read_text()),'embedding':runpy.run_path('/embedding-pins.py')['SPEC']}
    if root.is_symlink() or bundle.is_symlink():raise ValueError('Symlink directory rejected')
    if action=='backup':
        schema=sql('SELECT version_num FROM alembic_version')
        if schema!='0009_answer_feedback':raise ValueError('Current package schema required')
        bundle.mkdir(mode=0o700,exist_ok=False)
        try:
            subprocess.run(['pg_dump','--format=custom','--no-owner','--no-privileges','--file',str(bundle/'database.dump')],env=env,check=True,capture_output=True)
            with tarfile.open(bundle/'originals.tar','w') as archive:
                for path in sorted(root.glob('*')):
                    if path.is_symlink() or not path.is_file() or not re.fullmatch(r'[0-9a-f]{32}\.(pdf|txt)',path.name):raise ValueError('Unexpected original storage entry')
                    archive.add(path,arcname='originals/'+path.name,recursive=False)
            manifest={'format':'gov-private-backup-v1','schema':schema,'model_pins':pins,
                      'files':{n:digest(bundle/n) for n in ('database.dump','originals.tar')}}
            (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            for path in bundle.iterdir():path.chmod(0o600)
        except BaseException:
            # Keep failed bundle for inspection; never advertise it as complete.
            raise
        print('Private package backup complete; protect this directory and installation secrets.')
    else:
        manifest=json.loads((bundle/'manifest.json').read_text())
        if manifest.get('format')!='gov-private-backup-v1' or manifest.get('schema')!='0009_answer_feedback' or manifest.get('model_pins')!=pins:raise ValueError('Unsupported backup format/schema/model pins')
        if set(manifest['files'])!={'database.dump','originals.tar'} or any(digest(bundle/n)!=v for n,v in manifest['files'].items()):raise ValueError('Backup checksum mismatch')
        if sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")!='0':raise ValueError('Restore requires an empty database; existing data untouched')
        root.mkdir(parents=True,exist_ok=True)
        if any(root.iterdir()):raise ValueError('Restore requires empty original storage')
        with tarfile.open(bundle/'originals.tar','r') as archive:
            members=archive.getmembers()
            names=[m.name for m in members]
            if len(set(names))!=len(names) or any(not m.isfile() or not re.fullmatch(r'originals/[0-9a-f]{32}\.(pdf|txt)',m.name) for m in members):raise ValueError('Unsafe original archive')
            # Validate before writing. A failed restore is kept for diagnosis, never retried over nonempty data.
            subprocess.run(['pg_restore','--exit-on-error','--single-transaction','--no-owner','--no-privileges','--dbname=gov_package',str(bundle/'database.dump')],env=env,check=True,capture_output=True)
            for member in members:
                path=root/Path(member.name).name
                with archive.extractfile(member) as source,path.open('xb') as target:
                    import shutil
                    shutil.copyfileobj(source,target)
                path.chmod(0o600);os.chown(path,10001,10001)
        os.chown(root,10001,10001)
        print('Private package restore complete; verify originals and rebuild/reconcile vectors before Ask.')

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Backup/restore failed. Check stopped services, empty target and bundle checksums. No secrets printed.')
