"""Public-entry boundaries and real PostgreSQL auth with simulated HTTPS; no tunnel."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from demo_server import build_app,public_origin
from test_auth_postgres import postgres,api,REG,ORIGIN,signup_login

ORIGIN_URL='https://demo-check.trycloudflare.com'


def assets(tmp_path):
    (tmp_path/'assets').mkdir();(tmp_path/'index.html').write_text('<html>Built fixture</html>')
    (tmp_path/'assets/app.js').write_text('console.log("public asset")')
    return tmp_path


def test_public_routes_and_host_are_closed(tmp_path):
    app=build_app(ORIGIN_URL,assets(tmp_path),base_settings=Settings(_env_file=None))
    with TestClient(app,base_url=ORIGIN_URL) as c:
        assert c.get('/').status_code==200 and c.get('/assets/app.js').status_code==200
        for path in ('/admin/analytics','/admin/documents','/auth/admin/access','/auth/register','/docs','/redoc','/openapi.json','/health/ready','/.env','/runtime/native-services/api.log','/data/originals/test.pdf','/assets/%2e%2e/%2e%2e/.env'):
            assert c.get(path).status_code==404
        assert c.get('/',headers={'Host':'evil.example','X-Forwarded-Host':'demo-check.trycloudflare.com'}).status_code==400
        assert c.get('/',headers={'Host':'127.0.0.1'}).status_code==400
        assert "frame-ancestors 'none'" in c.get('/').headers['content-security-policy']
        for path in ('/assets/unknown.js','/assets/%5c%5cattacker.invalid%5cshare','/assets/C%3a%5cWindows%5cwin.ini','/assets/..%5c..%5c.env'):
            assert c.get(path).status_code==404
        assert c.get('/assets/app.js',headers={'Range':'bytes=0-1'}).content==b'console.log("public asset")'


@pytest.mark.parametrize('origin',['https://evil.example','http://demo-check.trycloudflare.com','https://*.trycloudflare.com','https://good.trycloudflare.com:443','https://good.trycloudflare.com/path','https://good.trycloudflare.com@evil.example'])
def test_public_hostname_validation(origin):
    with pytest.raises(ValueError):public_origin(origin)


def test_secure_cookie_origin_body_and_ownership(api,tmp_path):
    native,settings,engine=api
    signup_login(native)  # Dedicated test database; provisioning remains private.
    app=build_app(ORIGIN_URL,assets(tmp_path),base_settings=settings)
    app.state.engine.dispose();app.state.engine=engine
    app.state.sessions=sessionmaker(engine,expire_on_commit=False)
    h={'Origin':ORIGIN_URL,'X-CSRF-Protection':'1'}
    with TestClient(app,base_url=ORIGIN_URL) as c:
        r=c.post('/auth/login',json={'email':REG['email'],'password':REG['password']},headers=h)
        assert r.status_code==200
        cookie=r.headers['set-cookie'].lower()
        assert 'secure' in cookie and 'httponly' in cookie and 'samesite=strict' in cookie and 'path=/auth' in cookie
        assert c.post('/auth/refresh',headers=h).status_code==200
        assert c.post('/auth/refresh',headers={**h,'Origin':'https://evil.example','X-Forwarded-Proto':'https'}).status_code==403
        assert c.post('/auth/refresh',headers={'Origin':ORIGIN_URL}).status_code==403
        assert c.post('/ask',headers=h,content=b'x'*65537).status_code==413
        token=r.json()['access_token'];assert c.get('/auth/me',headers={'Authorization':'Bearer '+token}).status_code==200
        assert c.get('/ask/history').status_code==401
        assert c.get('/admin/analytics',headers={'Authorization':'Bearer '+token}).status_code==404
        assert c.post('/auth/register',json=REG,headers=h).status_code==404


def test_local_check_never_accepts_public_origin(tmp_path):
    with pytest.raises(ValueError):build_app(ORIGIN_URL,assets(tmp_path),local_check=True,base_settings=Settings(_env_file=None))


def test_planned_tunnel_lifecycle_without_network(monkeypatch,tmp_path):
    import demo
    import httpx
    calls=[];closed=[]
    monkeypatch.setattr(demo,'control',tmp_path)
    monkeypatch.setattr(demo,'check',lambda:None)
    monkeypatch.setattr(demo,'occupied',lambda port:False)
    monkeypatch.setenv('TUNNEL_TOKEN','test-only-inherited-value')
    class Process:
        def poll(self):return None
        def wait(self,timeout):return 0
    class Tree:
        def __init__(self,name):self.name=name
        def close(self):closed.append(self.name)
    def spawn(command,**kwargs):
        calls.append((command,kwargs))
        if len(calls)==1:
            kwargs['stdout'].write((ORIGIN_URL+'\n').encode());kwargs['stdout'].flush()
        return Process(),Tree('tunnel' if len(calls)==1 else 'entry')
    def probe(url,**kwargs):
        assert url=='http://127.0.0.1:8765/'
        assert kwargs['headers']['Host']=='demo-check.trycloudflare.com'
        assert kwargs['trust_env'] is False
        (tmp_path/'stop').touch()
        return httpx.Response(200)
    monkeypatch.setattr(demo,'spawn_owned',spawn)
    monkeypatch.setattr(httpx,'get',probe)
    demo.start()
    assert calls[0][0][1:]==['tunnel','--no-autoupdate','--url','http://127.0.0.1:8765','--metrics','127.0.0.1:20249']
    assert 'TUNNEL_TOKEN' not in calls[0][1]['env']
    assert calls[1][0][-2:]==['--origin',ORIGIN_URL]
    assert closed==['tunnel','entry']
