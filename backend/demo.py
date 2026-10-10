"""Explicit free demo preparation/lifecycle. Only start creates an external tunnel."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.request import urlretrieve
from filelock import FileLock,Timeout
from app.config import ROOT
from app.processes import spawn_owned
from demo_server import public_origin
from operate import occupied,preflight,external_owner

VERSION='2026.10.0'
SHA256='86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c'
control=ROOT/'runtime/demo-control';control.mkdir(parents=True,exist_ok=True)
binary=ROOT/'runtime/demo-tools/cloudflared.exe'


def validate_binary():
    if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest()!=SHA256:
        raise RuntimeError('Run demo prepare for pinned official cloudflared')
    result=subprocess.run([str(binary),'--version'],capture_output=True,text=True,check=True,timeout=10)
    if VERSION not in result.stdout:raise RuntimeError('Tunnel version mismatch')


def prepare():
    binary.parent.mkdir(parents=True,exist_ok=True)
    if not binary.exists():
        temporary=binary.with_suffix('.download')
        urlretrieve(f'https://github.com/cloudflare/cloudflared/releases/download/{VERSION}/cloudflared-windows-amd64.exe',temporary)
        if hashlib.sha256(temporary.read_bytes()).hexdigest()!=SHA256:raise RuntimeError('Tunnel checksum mismatch')
        temporary.replace(binary)
    validate_binary()
    env=os.environ.copy();env.update(VITE_API_BASE_URL='/',VITE_PUBLIC_DEMO='true')
    subprocess.run(['npm.cmd','--prefix','frontend','run','build','--','--outDir','../runtime/demo-frontend'],cwd=ROOT,env=env,check=True)
    print('Built demo frontend and pinned tunnel ready; no tunnel started, native configuration preserved.')


def check():
    settings=preflight();validate_binary()
    if not (ROOT/'runtime/demo-frontend/index.html').is_file():raise RuntimeError('Demo frontend missing')
    for name in ('worker','index','rag'):
        if not external_owner(name,settings):raise RuntimeError('Start required native owners first')
    import httpx
    with httpx.Client(trust_env=False,timeout=5) as client:
        if client.get('http://127.0.0.1:8011/health/ready').status_code!=200:raise RuntimeError('Index not ready')
        if client.get('http://127.0.0.1:11435/api/version').json()['version']!='0.17.1':raise RuntimeError('Project model runtime not ready')
    # Existing user cloudflared configuration would interfere with accountless Quick Tunnel.
    for name in ('config.yml','config.yaml'):
        if (Path.home()/'.cloudflared'/name).exists():raise RuntimeError('Existing cloudflared configuration needs explicit isolation; leave it unchanged')
    print('Local demo checks passed; external TLS/tunnel connectivity is unverified until explicit start.')


def start(local_check=False):
    check()
    if occupied(8765):raise RuntimeError('Entry port already occupied; no duplicate started')
    stop=control/'stop';stop.unlink(missing_ok=True)
    trees=[];processes=[]
    try:
        if local_check:origin='http://127.0.0.1:8765'
        else:
            # Do not bind the application until the generated hostname is validated.
            logpath=control/'tunnel.log'
            tunnel_env={k:v for k,v in os.environ.items() if not k.upper().startswith(('TUNNEL_','CLOUDFLARE_','GOV_'))}
            with logpath.open('wb') as log:
                process,tree=spawn_owned([str(binary),'tunnel','--no-autoupdate','--url','http://127.0.0.1:8765','--metrics','127.0.0.1:20249'],cwd=ROOT,env=tunnel_env,stdout=log,stderr=log)
            processes.append(process);trees.append(tree)
            deadline=time.monotonic()+60;origin=None
            while time.monotonic()<deadline and process.poll() is None:
                matches=re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',logpath.read_text(encoding='utf-8',errors='replace'))
                if matches:origin=public_origin(matches[-1]);break
                time.sleep(.2)
            if not origin:raise RuntimeError('Quick Tunnel did not provide a valid hostname; entry stays closed')
        with (control/'entry.log').open('ab') as log:
            command=[sys.executable,str(ROOT/'backend/demo_server.py'),'--origin',origin]
            if local_check:command.append('--local-check')
            process,tree=spawn_owned(command,cwd=ROOT,stdout=log,stderr=log)
        processes.append(process);trees.append(tree)
        import httpx
        deadline=time.monotonic()+30
        while time.monotonic()<deadline and process.poll() is None:
            try:
                r=httpx.get('http://127.0.0.1:8765/',headers={'Host':origin.split('://')[1]},trust_env=False,timeout=2)
                if r.status_code==200:break
            except httpx.HTTPError:pass
            time.sleep(.2)
        else:raise RuntimeError('Demo entry failed readiness; owned tunnel will close')
        print('Local check (no tunnel):' if local_check else 'Public demo:',origin,flush=True)
        print('Keep this terminal/laptop awake; Ctrl+C or demo stop closes only demo-owned processes.',flush=True)
        while not stop.exists() and all(p.poll() is None for p in processes):time.sleep(.2)
    finally:
        # Stop exposure before entry; native model/DB owners are untouched.
        for tree in trees:tree.close()
        for p in processes:p.wait(timeout=10)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','check','local-check','start','status','stop'));args=parser.parse_args()
    try:
        lock=FileLock(str(control/'owner.lock'),timeout=0)
        if args.action in ('status','stop'):
            try:
                with lock:print('Demo stopped; no owned tunnel/entry.')
            except Timeout:
                if args.action=='stop':(control/'stop').touch();print('Owned demo stop requested; wait for its terminal to finish.')
                else:print('Demo supervisor running (local-check or explicit tunnel); inspect its terminal.')
        else:
            with lock:
                if args.action=='prepare':prepare()
                elif args.action=='check':check()
                else:start(args.action=='local-check')
    except KeyboardInterrupt:print('Owned demo stopped; native services preserved.')
    except Timeout:raise SystemExit('Demo operation already owned; use demo status/stop and wait before another operation.')
    except Exception:raise SystemExit('Demo operation failed safely. Inspect private runtime/demo-control logs and SETUP. No credentials printed.')
