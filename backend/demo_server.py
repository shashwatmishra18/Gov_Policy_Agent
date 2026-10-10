"""Same-origin built frontend/API entry; never mount repository or private storage."""
import argparse
from pathlib import Path
from urllib.parse import urlsplit
import re
from fastapi import HTTPException
from starlette.responses import Response
from app.config import Settings, ROOT
from app.main import create_app
from app.request_limits import StrictHostMiddleware


def public_origin(value):
    if not re.fullmatch(r'https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com', value):
        raise ValueError('Exact HTTPS Quick Tunnel origin required')
    return value


class DemoBoundary:
    def __init__(self, app): self.app=app
    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http','websocket'):
            return await self.app(scope,receive,send)
        path=scope.get('path','')
        allowed=(path in ('/','/index.html') or path.startswith('/assets/')
                 or path in ('/auth/login','/auth/logout','/auth/refresh','/auth/me')
                 or path=='/search' or path.startswith('/search/')
                 or path=='/ask' or path.startswith('/ask/'))
        # Pre-provision ordinary demo accounts locally. No public admin or registration.
        if scope['type']!='http' or not allowed:
            if scope['type']=='websocket': return await send({'type':'websocket.close','code':1008})
            return await Response(status_code=404,headers={'Cache-Control':'no-store'})(scope,receive,send)
        async def secured(message):
            if message['type']=='http.response.start':
                message['headers'].extend([
                    (b'x-content-type-options',b'nosniff'),
                    (b'x-frame-options',b'DENY'),
                    (b'referrer-policy',b'no-referrer'),
                    (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
                ])
            await send(message)
        return await self.app(scope,receive,secured)


def build_app(origin, assets, *, local_check=False, base_settings=None):
    if local_check:
        if origin!='http://127.0.0.1:8765': raise ValueError('Fixed loopback local-check origin required')
    else: public_origin(origin)
    assets=Path(assets)
    if any(p.is_symlink() or p.is_junction() for p in (assets,assets/'index.html',assets/'assets')):
        raise ValueError('Symlink frontend root rejected')
    assets=assets.resolve()
    if not (assets/'index.html').is_file() or not (assets/'assets').is_dir():
        raise ValueError('Explicit demo frontend build required')
    base=base_settings or Settings()
    values=base.model_dump()
    values.update(environment='development' if local_check else 'production',
                  cookie_secure=not local_check,cors_origins=[origin])
    settings=Settings(_env_file=None,**values)
    app=create_app(settings)
    # Preload only generated JS/CSS. Never resolve an HTTP path on Windows:
    # Starlette 0.52 StaticFiles has an unresolved UNC/NTLM advisory.
    files={}
    for file in (assets/'assets').iterdir():
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(?:js|css)',file.name):
            raise ValueError('Unexpected frontend asset')
        if file.is_symlink() or file.is_junction() or not file.is_file() or file.stat().st_size>10_000_000:
            raise ValueError('Unsafe frontend asset')
        files[file.name]=(file.read_bytes(),'application/javascript' if file.suffix=='.js' else 'text/css')
    html=(assets/'index.html').read_bytes()
    @app.get('/assets/{name}')
    def asset(name: str):
        item=files.get(name)
        if item is None:raise HTTPException(404)
        return Response(item[0],media_type=item[1],headers={'Cache-Control':'public, max-age=3600'})
    @app.get('/')
    @app.get('/index.html')
    def frontend(): return Response(html,media_type='text/html',headers={'Cache-Control':'no-store'})
    app.add_middleware(DemoBoundary)
    # Unlike native diagnostics, this profile accepts only its exact entry hostname.
    app.add_middleware(StrictHostMiddleware,allowed_hosts=[urlsplit(origin).hostname],www_redirect=False)
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--origin',required=True)
    parser.add_argument('--local-check',action='store_true');args=parser.parse_args()
    import uvicorn
    app=build_app(args.origin,ROOT/'runtime/demo-frontend',local_check=args.local_check)
    # HTTPS terminates at Cloudflare. Do not trust arbitrary forwarded headers/IPs.
    uvicorn.run(app,host='127.0.0.1',port=8765,proxy_headers=False,access_log=False)
