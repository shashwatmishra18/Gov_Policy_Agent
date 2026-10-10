"""One Windows process owns the model and persistent Chroma; no automatic downloads."""
import argparse
from contextlib import asynccontextmanager
import threading
import time
import hmac
from pathlib import Path
from filelock import FileLock
from fastapi import FastAPI, Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app.config import Settings
from app.database import make_engine, schema_ready
from app.search_api import SearchInput, internal_key
from app.vector_index import Runtime, queue, status
from app.request_limits import BodyLimitMiddleware, StrictHostMiddleware


def service(runtime, key, hosts=None):
    guard = threading.Lock()
    stop = threading.Event()

    def jobs():
        while not stop.is_set():
            if guard.acquire(blocking=False):
                try: runtime.run_once()
                except Exception: pass  # Persisted lease recovers after DB outage.
                finally: guard.release()
            stop.wait(2)

    @asynccontextmanager
    async def lifespan(app):
        worker = threading.Thread(target=jobs, daemon=True); worker.start()
        yield
        stop.set(); worker.join(timeout=5)

    app = FastAPI(lifespan=lifespan, docs_url=None, openapi_url=None)
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(StrictHostMiddleware, allowed_hosts=hosts or ['127.0.0.1','localhost'], www_redirect=False)

    @app.get('/health/ready')
    def ready():
        # Runtime is constructed only after offline model validation and the owner lock.
        try:
            if not schema_ready(runtime.engine):raise ValueError('schema unavailable')
        except Exception:raise HTTPException(503,'Index database unavailable') from None
        return {'status':'ready'}

    def authorize(x_index_key: str = Header(default='')):
        if not hmac.compare_digest(x_index_key, key): raise HTTPException(403, 'Forbidden')

    @app.post('/query', dependencies=[Depends(authorize)])
    def query(body: SearchInput):
        if not guard.acquire(blocking=False): raise HTTPException(503, 'Index busy')
        try: return runtime.search(**body.model_dump())
        except ValueError as exc:
            if str(exc) == 'query_token_limit': raise HTTPException(422, 'Token limit') from None
            raise HTTPException(503, 'Index unavailable; inspect/reconcile') from None
        except Exception: raise HTTPException(503, 'Index unavailable') from None
        finally: guard.release()

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['serve','once','rebuild','status','reconcile'])
    args = parser.parse_args()
    settings = Settings(); engine = make_engine(settings)
    if not schema_ready(engine): raise SystemExit('Current PostgreSQL migration required')
    if args.command in ('rebuild','status'):
        with Session(engine) as db:
            print({'generation': str(queue(db).id)} if args.command == 'rebuild' else status(db))
    else:
        root = settings.data_dir.parent / 'vectors'; root.mkdir(parents=True, exist_ok=True)
        lock=settings.owner_path('index');lock.parent.mkdir(parents=True,exist_ok=True)
        with FileLock(str(lock), timeout=0):
            runtime = Runtime(settings, engine)
            if args.command == 'once': print({'job_processed': runtime.run_once()})
            elif args.command == 'reconcile': print(runtime.reconcile())
            else:
                import uvicorn
                container=settings.deployment_mode=='container_local'
                uvicorn.run(service(runtime, internal_key(settings), ['127.0.0.1','localhost','index'] if container else None), host='0.0.0.0' if container else '127.0.0.1', port=8011,
                    workers=1, access_log=False, proxy_headers=False)
