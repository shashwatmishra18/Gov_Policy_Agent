"""Create random installation secrets in an ignored directory, never native .env or accounts."""
import argparse
from pathlib import Path
import secrets
from app.config import ROOT
parser=argparse.ArgumentParser();parser.add_argument('--directory',default='runtime/docker-secrets');args=parser.parse_args()
root=(ROOT/args.directory).resolve()
if ROOT/'runtime' not in root.parents: raise SystemExit('Secrets must remain under ignored project runtime')
root.mkdir(parents=True,exist_ok=True)
for name in ('postgres_password','app_password','test_password','jwt_secret'):
    path=root/name
    if not path.exists():
        with path.open('x',encoding='utf-8') as f: f.write(secrets.token_urlsafe(48))
        path.chmod(0o600)
print('Private container secret files ready; existing secrets preserved, no credentials printed.')
