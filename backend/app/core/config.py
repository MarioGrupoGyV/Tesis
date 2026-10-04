"""Configuración explícita; ningún valor de producción se incluye en código."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test"] = "development"
    database_url: SecretStr | None = None
    database_url_file: Path | None = None
    csrf_secret: SecretStr | None = None
    csrf_secret_file: Path | None = None
    allowed_origins: str = "http://localhost:5173"
    session_cookie_secure: bool = False
    session_ttl_seconds: int = Field(default=28800, ge=60, le=86400)
    login_attempt_limit: int = Field(default=10, ge=1, le=100)
    login_window_seconds: int = Field(default=300, ge=1, le=3600)
    login_max_keys: int = Field(default=10000, ge=10, le=100000)
    import_storage_dir: Path | None = None
    ml_storage_dir: Path | None = None

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        if self.ml_storage_dir is not None:
            code_root = Path(__file__).resolve().parents[2]
            checkout = code_root.parent if code_root.name == 'backend' else code_root
            if not self.ml_storage_dir.is_absolute() or self.ml_storage_dir.resolve().is_relative_to(checkout):
                raise ValueError('ML_STORAGE_DIR debe estar fuera del checkout')
        if self.import_storage_dir is not None:
            code_root = Path(__file__).resolve().parents[2]
            checkout = code_root.parent if code_root.name == "backend" else code_root
            if not self.import_storage_dir.is_absolute() or self.import_storage_dir.resolve().is_relative_to(checkout):
                raise ValueError("IMPORT_STORAGE_DIR debe ser absoluto y estar fuera del checkout")
        if self.database_url_file is not None:
            self.database_url = SecretStr(self.database_url_file.read_text(encoding="utf-8").strip())
        if self.csrf_secret_file is not None:
            self.csrf_secret = SecretStr(self.csrf_secret_file.read_text(encoding="utf-8").strip())
        if self.database_url is None:
            raise ValueError("DATABASE_URL o DATABASE_URL_FILE es obligatorio")
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL debe usar PostgreSQL con psycopg")
        if self.csrf_secret is None or len(self.csrf_secret.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("CSRF_SECRET o CSRF_SECRET_FILE exige al menos 32 bytes")
        origins = self.origins
        if not origins:
            raise ValueError("ALLOWED_ORIGINS debe contener al menos un origen explícito")
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError("ALLOWED_ORIGINS solo admite orígenes HTTP(S) exactos sin rutas")
        if any(urlsplit(origin).scheme == "https" for origin in origins) and not self.session_cookie_secure:
            raise ValueError("Los orígenes HTTPS requieren SESSION_COOKIE_SECURE=true")
        return self

    @property
    def origins(self) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in self.allowed_origins.split(",") if value.strip()))

    @property
    def connection_url(self) -> str:
        assert self.database_url is not None
        return self.database_url.get_secret_value()

    @property
    def csrf_key(self) -> str:
        assert self.csrf_secret is not None
        return self.csrf_secret.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
