"""Fail early on invalid configuration; never load future services here."""
from pathlib import Path
import os
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GOV_", env_file=ROOT / ".env", env_file_encoding="utf-8",
        extra="forbid", hide_input_in_errors=True,
    )
    app_name: str = Field(default="Government Policy Assistant", min_length=1, max_length=100)
    deployment_mode: Literal['native', 'container_local'] = 'native'
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://127.0.0.1:5173"]
    db_host: str = '127.0.0.1'
    index_url: str = 'http://127.0.0.1:8011'
    locks_dir: Path | None = None
    llm_cpu_only: bool = False
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "gov_policy"
    db_user: str = "gov_app"
    db_password: SecretStr | None = None
    test_db_name: str = "gov_policy_test"
    test_db_user: str = "gov_test"
    test_db_password: SecretStr | None = None
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "gov-cs-028"
    jwt_audience: str = "gov-policy-web"
    access_minutes: int = Field(default=10, ge=1, le=30)
    refresh_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = False
    login_limit: int = Field(default=5, ge=2, le=20)
    throttle_seconds: int = Field(default=900, ge=10, le=3600)
    data_dir: Path = Path(os.environ.get("LOCALAPPDATA", str(ROOT / "runtime"))) / "GovPolicyAgent" / "data"
    upload_limit_bytes: int = Field(default=50 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    parser_seconds: int = Field(default=30, ge=1, le=60)
    max_pages: int = Field(default=500, ge=1, le=500)
    max_text_chars: int = Field(default=2_000_000, ge=100, le=2_000_000)
    job_lease_seconds: int = Field(default=45, ge=10, le=120)
    ocr_dpi: int = Field(default=300, ge=150, le=300)
    ocr_max_pixels: int = Field(default=12_000_000, ge=1_000_000, le=12_000_000)
    ocr_page_seconds: int = Field(default=30, ge=1, le=60)

    @field_validator("cors_origins")
    @classmethod
    def local_origins_only(cls, origins: list[str], info: ValidationInfo) -> list[str]:
        if not origins:
            raise ValueError("At least one explicit local origin is required")
        for origin in origins:
            parsed = urlsplit(origin)
            production = info.data.get("environment") == "production"
            allowed = (parsed.scheme == "https" and parsed.hostname is not None) if production else (
                parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port is not None)
            if (not allowed or parsed.username or parsed.password or parsed.path or parsed.query
                    or parsed.fragment):
                raise ValueError("Use explicit HTTPS production origins or 127.0.0.1 HTTP development origins")
        return list(dict.fromkeys(origins))

    @field_validator("db_name", "db_user", "test_db_name", "test_db_user")
    @classmethod
    def identifiers(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
            raise ValueError("Use lowercase PostgreSQL identifiers")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def strong_secret(cls, value: SecretStr | None):
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("JWT secret must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def secure_production(self):
        if self.deployment_mode == 'native':
            if self.db_host not in ('127.0.0.1','localhost') or self.index_url != 'http://127.0.0.1:8011':
                raise ValueError('Native database/index must remain loopback')
        elif self.db_host != 'postgres' or self.index_url != 'http://index:8011':
            raise ValueError('Container mode requires explicit private Compose service addresses')
        if self.environment == "production" and not self.cookie_secure:
            raise ValueError("Production requires Secure cookies and HTTPS")
        if self.db_name == self.test_db_name:
            raise ValueError("Test database must differ from application database")
        return self

    def owner_path(self, name):
        return (self.locks_dir / (name+'.lock')) if self.locks_dir else {
            'index': self.data_dir.parent/'vectors/owner.lock',
            'rag': self.data_dir.parent/'ollama/owner.lock',
            'ingestion': self.data_dir.parent/'ingestion-owner.lock'}[name]
