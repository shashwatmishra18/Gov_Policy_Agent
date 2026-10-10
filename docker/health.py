import sys,time
from pathlib import Path
import httpx
from sqlalchemy.orm import Session
from app.config import Settings
from app.database import make_engine,schema_ready
from app.answer_models import AnswerWorker
from app.auth import now
s=Settings();service=sys.argv[1]
if service in ('api','index'):
    url='http://127.0.0.1:'+('8000' if service=='api' else '8011')+'/health/ready'
    assert httpx.get(url,trust_env=False,timeout=3).status_code==200
else:
    engine=make_engine(s);assert schema_ready(engine)
    if service=='rag':
        with Session(engine) as db:
            marker=db.get(AnswerWorker,1);assert marker and (now()-marker.heartbeat).total_seconds()<30
        assert httpx.get('http://127.0.0.1:11435/api/version',trust_env=False,timeout=3).json()['version']=='0.17.1'
    else: assert time.time()-float((s.locks_dir/'ingestion.ready').read_text())<90
    engine.dispose()
