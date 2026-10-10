"""Private, interactive local setup/admin commands. Never pass secrets as arguments."""
import argparse
from getpass import getpass, GetPassWarning
from pathlib import Path
import secrets
import sys
import warnings

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import dotenv_values, set_key
import psycopg
from psycopg import sql
from sqlalchemy import select, text, update, func
from sqlalchemy.orm import Session

from app.config import ROOT, Settings
from app.database import make_engine
from app.models import User, AuthSession
from app.schemas import Registration
from pwdlib import PasswordHash


def configure():
    env = ROOT / ".env"
    existing = dotenv_values(env) if env.exists() else {}
    for key, expected in {"GOV_DB_NAME": "gov_policy", "GOV_DB_USER": "gov_app",
                          "GOV_TEST_DB_NAME": "gov_policy_test", "GOV_TEST_DB_USER": "gov_test"}.items():
        if existing.get(key) and existing[key] != expected:
            raise ValueError("Refusing to overwrite custom database configuration")
    administrator_password = getpass("PostgreSQL postgres password (hidden): ")
    credentials = {}
    with psycopg.connect(host="127.0.0.1", port=5432, dbname="postgres", user="postgres",
                         password=administrator_password, connect_timeout=3, autocommit=True) as connection:
        addresses = connection.execute("SHOW listen_addresses").fetchone()[0]
        if addresses not in {"localhost", "127.0.0.1", "127.0.0.1,::1"}:
            connection.execute("ALTER SYSTEM SET listen_addresses = 'localhost'")
            print("Loopback-only setting saved. In administrator PowerShell run:")
            print("Restart-Service postgresql-x64-18")
            print("Then run configure again. No application credentials changed yet.")
            return
        for role, database, prefix in [("gov_app", "gov_policy", "GOV_DB"),
                                       ("gov_test", "gov_policy_test", "GOV_TEST_DB")]:
            present = connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            password = existing.get(f"{prefix}_PASSWORD")
            if present and not password:
                password = getpass(f"Existing {role} password (hidden): ")
            password = password or secrets.token_urlsafe(36)
            # Save privately before provisioning so interruption cannot lose a newly generated role password.
            set_key(str(env), f"{prefix}_PASSWORD", password, quote_mode="always")
            if not present:
                connection.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
            role_flags = connection.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname=%s", (role,)).fetchone()
            if any(role_flags):
                raise ValueError("Dedicated role has excessive privileges; resolve privately before continuing")
            owner = connection.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s", (database,)).fetchone()
            if owner is None:
                connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(role)))
            elif owner[0] != role:
                raise ValueError("Existing database has unexpected ownership; no changes made to it")
            connection.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
            with psycopg.connect(host="127.0.0.1", port=5432, dbname=database, user=role,
                                 password=password, connect_timeout=3) as app_connection:
                app_connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            credentials[f"{prefix}_NAME"] = database
            credentials[f"{prefix}_USER"] = role
            credentials[f"{prefix}_PASSWORD"] = password
    credentials["GOV_JWT_SECRET"] = existing.get("GOV_JWT_SECRET") or secrets.token_urlsafe(48)
    credentials["GOV_CORS_ORIGINS"] = '["http://127.0.0.1:5173"]'
    for key, value in credentials.items():
        set_key(str(env), key, value, quote_mode="always")
    print("Private .env configured; app/test roles and databases verified. No passwords printed.")
    print("Next: .\\.venv\\Scripts\\python.exe -m alembic -c backend/alembic.ini upgrade head")


def bootstrap_admin():
    settings = Settings()
    email = input("Admin email: ").strip()
    username = input("Admin username: ").strip()
    password = getpass("Admin password (12–128 characters, hidden): ")
    if password != getpass("Repeat admin password (hidden): "):
        raise ValueError("Passwords do not match")
    registration = Registration(email=email, username=username, password=password)
    engine = make_engine(settings)
    with Session(engine) as session:
        session.execute(text("SELECT pg_advisory_xact_lock(28003)"))
        if session.scalar(select(User.id).where(User.role == "admin")):
            raise ValueError("An admin already exists; this command bootstraps the first admin only")
        session.add(User(email=str(registration.email).lower(), username=registration.username,
                         password_hash=PasswordHash.recommended().hash(password), role="admin"))
        session.commit()
    engine.dispose()
    print("First admin created. No default credentials were used.")


def hidden_password():
    """Never fall back to echoing a password when the terminal is unsuitable."""
    if not sys.stdin.isatty():
        raise ValueError("Interactive terminal required")
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        password = getpass("New password (12-128 characters, hidden): ")
        repeated = getpass("Repeat new password (hidden): ")
    if password != repeated or not 12 <= len(password) <= 128:
        raise ValueError("Invalid password or confirmation")
    return password


def reset_account(engine, user_id, password):
    """Atomically replace a selected active account's password and revoke sessions."""
    if not 12 <= len(password) <= 128:
        raise ValueError("Invalid password length")
    encoded = PasswordHash.recommended().hash(password)
    with Session(engine) as session, session.begin():
        selected = session.execute(select(User.id, User.active).where(
            User.id == user_id).with_for_update()).one_or_none()
        if selected is None or not selected.active:
            raise ValueError("Active account required")
        session.execute(update(User).where(User.id == user_id).values(password_hash=encoded))
        session.execute(update(AuthSession).where(AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None)).values(revoked_at=func.now()))


def provision_user(engine, registration):
    """Local provisioning always creates an ordinary account, never an administrator."""
    with Session(engine) as session, session.begin():
        session.add(User(email=str(registration.email), username=registration.username,
            password_hash=PasswordHash.recommended().hash(registration.password.get_secret_value()),
            preferred_language=registration.preferred_language, role="user"))


def recover_account():
    engine = make_engine(Settings())
    try:
        with Session(engine) as session:
            accounts = session.execute(select(User.id, User.email, User.username,
                User.role, User.active, User.created_at).order_by(User.created_at)).all()
        print("Private local account selection. Do not copy this list into chat.")
        admins = [account for account in accounts if account.role == "admin"]
        for number, account in enumerate(accounts, 1):
            note = " (original bootstrap administrator candidate)" if account.role == "admin" and len(admins) == 1 else ""
            print(f"{number}. {account.email} | {account.username} | {account.role} | active={account.active}{note}")
        choice = input("Choose your account number, N for a new ordinary account, or Enter to cancel: ").strip()
        if not choice:
            print("Cancelled; no account changed.")
            return
        if choice.lower() == "n":
            email = input("New ordinary account email: ").strip()
            username = input("New ordinary account username: ").strip()
            provision_user(engine, Registration(email=email, username=username, password=hidden_password()))
            print("Ordinary account created. No existing accounts changed.")
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(accounts):
            raise ValueError("Invalid selection")
        account = accounts[int(choice) - 1]
        if not account.active:
            raise ValueError("Inactive account cannot be recovered with this command")
        if input("Reset only this selected account? Type RESET to confirm: ").strip() != "RESET":
            print("Cancelled; no account changed.")
            return
        reset_account(engine, account.id, hidden_password())
        print("Password recovered; all existing sessions revoked. Account identity and role preserved.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["configure", "bootstrap-admin", "recover-account"])
    args = parser.parse_args()
    try:
        if not sys.stdin.isatty():
            raise ValueError("Use an interactive local terminal for hidden input")
        {"configure": configure, "bootstrap-admin": bootstrap_admin,
         "recover-account": recover_account}[args.command]()
    except Exception:
        # Do not echo DB exceptions/DSNs, validation inputs or passwords.
        print("Command failed. Check local service, credentials, input and database ownership; no secret details printed.", file=sys.stderr)
        sys.exit(1)
