"""Local dotenv loading must never replace an explicit runtime/test destination."""

import pytest

from app.core import config


@pytest.fixture
def local_env(tmp_path, monkeypatch):
    for name in config.Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    env_file = tmp_path / "backend.env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://test@localhost/config_test\n"
        "CSRF_SECRET=config-test-only-secret-at-least-32-characters\n"
        "ALLOWED_ORIGINS=http://localhost:5173\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "_LOCAL_ENV_FILE", env_file)
    config.get_settings.cache_clear()
    yield env_file
    config.get_settings.cache_clear()


def test_local_env_loads_independently_of_working_directory(local_env, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:9000")
    settings = config.get_settings()
    assert settings.connection_url == "postgresql+psycopg://test@localhost/config_test"
    assert settings.origins == ["http://localhost:9000"]


@pytest.mark.parametrize("use_file", [False, True])
def test_explicit_connection_ignores_local_secret_files(local_env, tmp_path, monkeypatch, use_file):
    local_env.write_text(
        "DATABASE_URL_FILE=missing-local-database-secret\n"
        "CSRF_SECRET_FILE=missing-local-csrf-secret\n",
        encoding="utf-8",
    )
    runtime_url = "postgresql+psycopg://test@localhost/runtime_test"
    if use_file:
        runtime_file = tmp_path / "runtime-url"
        runtime_file.write_text(runtime_url, encoding="utf-8")
        monkeypatch.setenv("DATABASE_URL_FILE", str(runtime_file))
    else:
        monkeypatch.setenv("DATABASE_URL", runtime_url)
    monkeypatch.setenv("CSRF_SECRET", "runtime-test-only-secret-at-least-32-characters")
    assert config.get_settings().connection_url == runtime_url


def test_test_environment_never_falls_back_to_local_connection(local_env, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    with pytest.raises(ValueError, match="DATABASE_URL o DATABASE_URL_FILE es obligatorio"):
        config.get_settings()
