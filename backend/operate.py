"""Native operations: preflight, idempotent start/status, verified-owner-only stop."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from filelock import FileLock,Timeout
from app.config import ROOT,Settings
from app.database import make_engine,schema_ready
from app.embedding import model_path,SPEC

registry=ROOT/'runtime/native-services';registry.mkdir(parents=True,exist_ok=True)
python=ROOT/'.venv/Scripts/python.exe'
services={
 'api':([str(python),'-m','uvicorn','app.main:app','--app-dir',str(ROOT/'backend'),'--host','127.0.0.1','--port','8000','--no-access-log','--no-proxy-headers'],ROOT,8000),
 'frontend':([shutil.which('node') or 'node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','5173','--strictPort'],ROOT/'frontend',5173),
 'worker':([str(python),str(ROOT/'backend/worker.py')],ROOT,None),
 'index':([str(python),str(ROOT/'backend/index.py'),'serve'],ROOT,8011),
 'rag':([str(python),str(ROOT/'backend/rag.py')],ROOT,11435)}

def process_identity(pid):
    """Query a fixed numeric PID; never expose command lines or private environment."""
    pid=int(pid)
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
        f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; if($p){{@{{created=$p.CreationDate.ToUniversalTime().Ticks.ToString(); command=$p.CommandLine}} | ConvertTo-Json -Compress}}"],
        capture_output=True,text=True,check=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(result.stdout) if result.stdout.strip() else None

def running(name):
    path=registry/(name+'.owner.json')
    if not path.exists():return None
    record=json.loads(path.read_text())
    try:
        p=process_identity(record['pid'])
        if not p or p['created']!=record['created'] or str(ROOT/'backend/service_owner.py') not in (p['command'] or ''):return None
        return record
    except (ValueError,KeyError):return None

def occupied(port):
    if port is None:return False
    with socket.socket() as s:s.settimeout(.2);return s.connect_ex(('127.0.0.1',port))==0

def external_owner(name,s):
    if occupied(services[name][2]):return True
    if name in ('worker','index','rag'):
        key={'worker':'ingestion','index':'index','rag':'rag'}[name]
        try:
            with FileLock(str(s.owner_path(key)),timeout=0):pass
        except Timeout:return True
    return False

def preflight():
    if os.name!='nt' or not python.exists() or not shutil.which('node'):raise RuntimeError('Native Windows Python/Node setup required')
    s=Settings();engine=make_engine(s)
    if not s.jwt_secret or not s.db_password:raise RuntimeError('Private authentication/database configuration missing')
    binary=Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe'
    if not binary.is_file():raise RuntimeError('Pinned Ollama installation missing')
    try:
        if not schema_ready(engine):raise RuntimeError('Database/schema not ready; see SETUP')
    finally:engine.dispose()
    for path in (ROOT/'frontend/node_modules/vite/bin/vite.js',model_path(s)/'gov-model.json',s.data_dir.parent/'ollama/prepared.json',s.data_dir.parent/'ollama/tokenizer/tokenizer.json'):
        if not path.is_file():raise RuntimeError('Dependencies/model preparation missing; see SETUP')
    if json.loads((model_path(s)/'gov-model.json').read_text())!=SPEC:raise RuntimeError('Encoder pin mismatch')
    if json.loads((s.data_dir.parent/'ollama/prepared.json').read_text())!=json.loads((ROOT/'docs/llm_model.json').read_text()):raise RuntimeError('Generation model pin mismatch')
    from app.ocr import prepared
    prepared(s)
    print('Native dependency/config/schema/model-manifest/OCR preflight passed; no model loaded.')
    return s

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('preflight','start','status','stop'))
    parser.add_argument('--services',nargs='+',choices=tuple(services),default=list(services));args=parser.parse_args()
    with FileLock(str(registry/'operation.lock'),timeout=0):
        s=preflight() if args.action in ('preflight','start') else Settings()
        if args.action=='preflight':return
        selected=list(dict.fromkeys(args.services))
        for name in (reversed(selected) if args.action=='stop' else selected):
            owner=running(name)
            if args.action=='status':print(name, 'managed running' if owner else 'existing unmanaged owner/port' if external_owner(name,s) else 'stopped');continue
            if args.action=='stop':
                if not owner:print(name,'no managed owner; untouched');continue
                (registry/(name+'.stop')).touch()
                deadline=time.monotonic()+15
                while running(name) and time.monotonic()<deadline:time.sleep(.2)
                if running(name):raise RuntimeError('Managed supervisor did not stop; inspect it')
                print(name,'owned process tree stopped; durable jobs recover on restart');continue
            if owner or external_owner(name,s):print(name,'already running; no duplicate started');continue
            command,cwd,port=services[name];stop=registry/(name+'.stop');stop.unlink(missing_ok=True)
            spec=registry/(name+'.spec.json');spec.write_text(json.dumps({'command':command,'cwd':str(cwd),'stop':str(stop)}))
            with (registry/(name+'.log')).open('ab') as log:
                p=subprocess.Popen([str(python),str(ROOT/'backend/service_owner.py'),str(spec)],cwd=ROOT,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
            identity=process_identity(p.pid)
            if not identity:raise RuntimeError('Service startup failed; inspect private service log')
            record={'pid':p.pid,'created':identity['created']}
            (registry/(name+'.owner.json')).write_text(json.dumps(record));time.sleep(.3)
            if p.poll() is not None:raise RuntimeError('Service startup failed; inspect private service log')
            print(name,'started; readiness may take time, inspect status/System status')

if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('Operation failed; inspect dependencies, owner status and private logs. No credentials printed.')
