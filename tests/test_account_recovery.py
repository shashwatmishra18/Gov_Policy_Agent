"""Private recovery against the guarded disposable PostgreSQL database."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from getpass import GetPassWarning
from uuid import UUID, uuid4
import warnings

import pytest
from sqlalchemy import select, update, event
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

import manage
from app import auth
from app.models import User
from app.schemas import Registration
from test_auth_postgres import postgres, api, signup_login, auth_header, ORIGIN, REG

NEW = "Synthetic-recovery-password-456"
LOGIN = {key: REG[key] for key in ('email', 'password')}


def test_reset_revokes_all_sessions_preserves_accounts(api):
    client, _, engine = api
    first, cookie = signup_login(client)
    second = client.post('/auth/login', headers=ORIGIN, json=LOGIN).json()
    other = Registration(email='other@example.com', username='other_user', password=NEW)
    manage.provision_user(engine, other)
    unrelated = client.post('/auth/login', headers=ORIGIN,
        json={'email': str(other.email), 'password': NEW}).json()
    user_id = UUID(first['user']['id'])
    # Test the original bootstrap case without changing any live account.
    with engine.begin() as connection:
        connection.execute(update(User).where(User.id == user_id).values(role='admin'))
    with Session(engine) as db:
        before = db.execute(select(User.email, User.username, User.role,
            User.active, User.preferred_language, User.created_at).where(User.id == user_id)).one()
    manage.reset_account(engine, user_id, NEW)
    for result in (first, second):
        assert client.get('/auth/me', headers=auth_header(result['access_token'])).status_code == 401
    client.cookies.clear()
    client.cookies.set(auth.COOKIE, cookie, path='/auth')
    assert client.post('/auth/refresh', headers=ORIGIN).status_code == 401
    assert client.get('/auth/me', headers=auth_header(unrelated['access_token'])).status_code == 200
    assert client.post('/auth/login', headers=ORIGIN, json=LOGIN).status_code == 401
    assert client.post('/auth/login', headers=ORIGIN, json={**LOGIN, 'password': NEW}).status_code == 200
    with Session(engine) as db:
        after = db.execute(select(User.email, User.username, User.role,
            User.active, User.preferred_language, User.created_at).where(User.id == user_id)).one()
    assert before == after
    assert after.role == 'admin'
    assert unrelated['user']['role'] == 'user'
    with pytest.raises(IntegrityError):
        manage.provision_user(engine, other)
    assert client.get('/auth/me', headers=auth_header(unrelated['access_token'])).status_code == 200


def test_invalid_reset_does_not_change_account(api):
    client, _, engine = api
    result, _ = signup_login(client)
    user_id = UUID(result['user']['id'])
    for target, password in ((user_id, 'short'), (uuid4(), NEW)):
        with pytest.raises(ValueError):
            manage.reset_account(engine, target, password)
    assert client.get('/auth/me', headers=auth_header(result['access_token'])).status_code == 200
    with engine.begin() as connection:
        connection.execute(update(User).where(User.id == user_id).values(active=False))
    with pytest.raises(ValueError):
        manage.reset_account(engine, user_id, NEW)
    with Session(engine) as db:
        assert db.scalar(select(User.active).where(User.id == user_id)) is False


def test_login_in_flight_is_revoked_by_reset(api, monkeypatch):
    client, _, engine = api
    initial, _ = signup_login(client)
    user_id = UUID(initial['user']['id'])
    entered, release, resetting = Event(), Event(), Event()
    original = auth.password_hash

    class PausedVerifier:
        def verify(self, *args):
            entered.set()
            assert release.wait(10)
            return original.verify(*args)

    monkeypatch.setattr(auth, 'password_hash', PausedVerifier())
    def reached_lock(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT users.id, users.active') and 'FOR UPDATE' in statement:
            resetting.set()
    event.listen(engine, 'before_cursor_execute', reached_lock)
    def reset():
        manage.reset_account(engine, user_id, NEW)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            login = pool.submit(client.post, '/auth/login', headers=ORIGIN, json=LOGIN)
            assert entered.wait(10)
            recovery = pool.submit(reset)
            try:
                assert resetting.wait(10)
                with pytest.raises(TimeoutError):
                    recovery.result(timeout=0.3)
            finally:
                release.set()
            response = login.result(timeout=15)
            recovery.result(timeout=15)
    finally:
        event.remove(engine, 'before_cursor_execute', reached_lock)
    assert response.status_code == 200
    assert client.get('/auth/me', headers=auth_header(response.json()['access_token'])).status_code == 401


def test_hidden_input_refuses_echo_and_mismatch(monkeypatch):
    monkeypatch.setattr(manage.sys.stdin, 'isatty', lambda: True)
    def unsafe(prompt):
        warnings.warn('Echo fallback', GetPassWarning)
        return NEW
    monkeypatch.setattr(manage, 'getpass', unsafe)
    with pytest.raises(GetPassWarning):
        manage.hidden_password()
    values = iter((NEW, NEW + 'different'))
    monkeypatch.setattr(manage, 'getpass', lambda prompt: next(values))
    with pytest.raises(ValueError):
        manage.hidden_password()
    monkeypatch.setattr(manage.sys.stdin, 'isatty', lambda: False)
    with pytest.raises(ValueError):
        manage.hidden_password()
