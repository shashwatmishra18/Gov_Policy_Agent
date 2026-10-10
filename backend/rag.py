"""Exclusive Windows local RAG worker and contained Ollama owner."""
import asyncio
from filelock import FileLock
from sqlalchemy.orm import Session
from app.config import Settings
from app.database import make_engine,schema_ready
from app.ollama_local import OllamaHost
from app.answer_worker import Worker
from app.answer_models import AnswerWorker
from app.auth import now
from datetime import timedelta

async def serve(worker):
    while True:
        if not await worker.once(): await asyncio.sleep(0.2)

if __name__=='__main__':
    from app.processes import install_shutdown
    install_shutdown()
    settings=Settings();engine=make_engine(settings)
    if not schema_ready(engine): raise SystemExit('Current PostgreSQL migration required')
    root=settings.data_dir.parent/'ollama';root.mkdir(parents=True,exist_ok=True)
    try:
        lock=settings.owner_path('rag');lock.parent.mkdir(parents=True,exist_ok=True)
        with FileLock(str(lock),timeout=0),OllamaHost(settings) as host:
            worker=Worker(settings,engine,host);worker.recover()
            print('Local RAG worker ready; one pending job; project Ollama 127.0.0.1:11435. Ctrl+C to stop.',flush=True)
            try: asyncio.run(serve(worker))
            finally:
                with Session(engine) as db:
                    marker=db.get(AnswerWorker,1)
                    if marker: marker.heartbeat=now()-timedelta(days=1);db.commit()
    except KeyboardInterrupt: pass
    finally: engine.dispose()
