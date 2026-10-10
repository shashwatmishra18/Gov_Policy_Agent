"""Local auth with DB-backed sessions, atomic rotation and durable throttling."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from pwdlib import PasswordHash
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, AuthThrottle, User
from .schemas import Login, ProfileUpdate, Registration, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)
password_hash = PasswordHash.recommended()
# Constant dummy hash prevents the missing-user path from skipping Argon2 work.
DUMMY_HASH = password_hash.hash(secrets.token_urlsafe(32))
COOKIE = "gov_refresh"


def now():
    return datetime.now(timezone.utc)


def secret(settings):
    if settings.jwt_secret is None:
        raise HTTPException(503, "Authentication is not configured")
    return settings.jwt_secret.get_secret_value()


def csrf(request: Request):
    if (request.headers.get("origin") not in request.app.state.settings.cors_origins
            or request.headers.get("x-csrf-protection") != "1"):
        raise HTTPException(403, "Untrusted request origin or missing CSRF protection")


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_refresh(session_id: UUID):
    return f"{session_id}.{secrets.token_urlsafe(48)}"


def set_cookie(response: Response, token: str, session: AuthSession, settings):
    response.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure,
                        samesite="strict", path="/auth",
                        max_age=max(0, int((session.expires_at - now()).total_seconds())))


def clear_cookie(response: Response, settings):
    response.delete_cookie(COOKIE, path="/auth", secure=settings.cookie_secure,
                           httponly=True, samesite="strict")


def token_response(user: User, session: AuthSession, settings):
    timestamp = now()
    token = jwt.encode({"sub": str(user.id), "sid": str(session.id), "jti": str(uuid4()),
                        "iat": timestamp, "nbf": timestamp,
                        "exp": timestamp + timedelta(minutes=settings.access_minutes),
                        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
                        "token_use": "access"}, secret(settings), algorithm="HS256")
    return TokenResponse(access_token=token, expires_in=settings.access_minutes * 60,
                         user=UserResponse.model_validate(user))


def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    try:
        claims = jwt.decode(credentials.credentials, secret(settings), algorithms=["HS256"],
                            issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                            options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "sid", "jti", "token_use"]})
        user_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
        if claims["token_use"] != "access":
            raise ValueError("Wrong token type")
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(401, "Invalid or expired session", headers={"WWW-Authenticate": "Bearer"}) from None
    session = db.get(AuthSession, session_id)
    user = db.get(User, user_id)
    if (session is None or session.user_id != user_id or session.revoked_at is not None
            or session.expires_at <= now() or user is None or not user.active):
        raise HTTPException(401, "Invalid or expired session")
    return user


def admin_user(user: User = Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return user


def throttle(db: Session, request: Request, email: str, action: str):
    settings = request.app.state.settings
    key_secret = secret(settings).encode()
    ip = request.client.host if request.client else "unknown"
    limits = [(f"{action}:ip:{ip}", settings.login_limit * 10)]
    if action == "login":
        limits.append((f"{action}:account:{email}", settings.login_limit))
    timestamp = now()
    # Serializes bounded table cleanup/creation; never trusts forwarded headers.
    db.execute(text("SELECT pg_advisory_xact_lock(28002)"))
    db.execute(delete(AuthThrottle).where(AuthThrottle.window_start < timestamp - timedelta(seconds=settings.throttle_seconds * 2)))
    if db.scalar(select(func.count()).select_from(AuthThrottle)) >= 10000:
        db.commit()
        raise HTTPException(429, "Too many authentication attempts; try later")
    blocked = False
    for raw_key, limit in sorted(limits):
        key = hmac.new(key_secret, raw_key.encode(), hashlib.sha256).hexdigest()
        db.execute(insert(AuthThrottle).values(key=key, attempts=0, window_start=timestamp).on_conflict_do_nothing())
        record = db.scalar(select(AuthThrottle).where(AuthThrottle.key == key).with_for_update())
        if (timestamp - record.window_start).total_seconds() >= settings.throttle_seconds:
            record.attempts, record.window_start = 0, timestamp
        if record.attempts >= limit:
            blocked = True
        else:
            record.attempts += 1
    db.commit()  # Must survive wrong-password responses and backend restarts.
    if blocked:
        raise HTTPException(429, "Too many authentication attempts; try later",
                            headers={"Retry-After": str(settings.throttle_seconds)})


@router.post("/register", response_model=UserResponse, status_code=201, dependencies=[Depends(csrf)])
def register(body: Registration, request: Request, db: Session = Depends(get_db)):
    throttle(db, request, str(body.email).lower(), "register")
    user = User(email=str(body.email).lower(), username=body.username,
                password_hash=password_hash.hash(body.password.get_secret_value()),
                preferred_language=body.preferred_language, role="user")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email or username is already registered") from None
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(csrf)])
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    throttle(db, request, body.email, "login")
    # Serialize password verification/session creation with private local recovery.
    user = db.scalar(select(User).where(User.email == body.email).with_for_update())
    valid = password_hash.verify(body.password.get_secret_value(), user.password_hash if user else DUMMY_HASH)
    if not valid or user is None or not user.active:
        raise HTTPException(401, "Invalid email or password")
    session = AuthSession(id=uuid4(), user_id=user.id, expires_at=now() + timedelta(days=settings.refresh_days))
    token = new_refresh(session.id)
    session.refresh_hash, session.used_hashes = digest(token), []
    db.add(session)
    db.commit()
    set_cookie(response, token, session, settings)
    return token_response(user, session, settings)


def cookie_session(request, db):
    token = request.cookies.get(COOKIE, "")
    if len(token) > 200:
        return None, ""
    try:
        session_id = UUID(token.split(".", 1)[0])
    except ValueError:
        return None, ""
    return db.scalar(select(AuthSession).where(AuthSession.id == session_id).with_for_update()), digest(token)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(csrf)])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    secret(settings)
    session, token_hash = cookie_session(request, db)
    if session is None or session.revoked_at is not None or session.expires_at <= now():
        raise HTTPException(401, "Session expired; sign in again")
    if not hmac.compare_digest(token_hash, session.refresh_hash):
        if token_hash in session.used_hashes:
            session.revoked_at = now()
            db.commit()
        raise HTTPException(401, "Invalid refresh token; sign in again")
    user = db.get(User, session.user_id)
    if user is None or not user.active or len(session.used_hashes) >= 256:
        session.revoked_at = now()
        db.commit()
        raise HTTPException(401, "Session expired; sign in again")
    token = new_refresh(session.id)
    session.used_hashes = [*session.used_hashes, session.refresh_hash]
    session.refresh_hash, session.rotated_at = digest(token), now()
    db.commit()  # Row lock covers compare, consume and rotation in one transaction.
    set_cookie(response, token, session, settings)
    return token_response(user, session, settings)


@router.post("/logout", status_code=204, dependencies=[Depends(csrf)])
def logout(request: Request, response: Response, credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
           db: Session = Depends(get_db)):
    session, token_hash = cookie_session(request, db)
    if session is not None and (hmac.compare_digest(token_hash, session.refresh_hash) or token_hash in session.used_hashes):
        session.revoked_at = now()
        db.commit()
    # Missing browser cookie must not leave a valid submitted access session alive.
    if credentials is not None:
        settings = request.app.state.settings
        try:
            claims = jwt.decode(credentials.credentials, secret(settings), algorithms=["HS256"],
                                issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "sid", "jti", "token_use"]})
            if claims["token_use"] == "access":
                access_session = db.get(AuthSession, UUID(claims["sid"]))
                if access_session is not None and access_session.user_id == UUID(claims["sub"]):
                    access_session.revoked_at = now()
                    db.commit()
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            pass
    clear_cookie(response, request.app.state.settings)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserResponse, dependencies=[Depends(csrf)])
def update_profile(body: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.preferred_language = body.preferred_language
    db.commit()
    db.refresh(user)
    return user


@router.get("/admin/access")
def admin_access(user: User = Depends(admin_user)):
    return {"authorized": True, "user_id": str(user.id), "role": user.role}
