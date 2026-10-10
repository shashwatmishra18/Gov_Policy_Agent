"""Fixed Compose secrets and explicit service commands; never logs private configuration."""
import os
from pathlib import Path
import sys

for name,field in [('app_password','GOV_DB_PASSWORD'),('test_password','GOV_TEST_DB_PASSWORD'),('jwt_secret','GOV_JWT_SECRET')]:
    value=(Path('/run/secrets')/name).read_text().strip()
    if not 32 <= len(value) <= 200 or value.startswith('CHANGE'): raise SystemExit('Private container setup required')
    os.environ[field]=value
commands={
 'api':[sys.executable,'-m','uvicorn','app.main:app','--app-dir','backend','--host','0.0.0.0','--port','8000','--no-access-log','--no-proxy-headers'],
 'migrate':[sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],
 'worker':[sys.executable,'backend/worker.py'], 'index':[sys.executable,'backend/index.py','serve'],
 'rag':[sys.executable,'backend/rag.py'], 'admin':[sys.executable,'backend/manage.py','bootstrap-admin'],
 'prepare-embedding':[sys.executable,'backend/prepare_model.py'], 'prepare-llm':[sys.executable,'backend/prepare_llm.py'],
 'prepare-ocr':[sys.executable,'backend/prepare_ocr.py',*sys.argv[2:]],
 'health':[sys.executable,'docker/health.py',*sys.argv[2:]],
 'init':[sys.executable,'docker/init_state.py']}
command=commands.get(sys.argv[1])
if command is None: raise SystemExit('Unknown container command')
os.execvp(command[0],command)
