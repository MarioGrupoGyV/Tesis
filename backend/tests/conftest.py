"""S1 integration fixtures: PostgreSQL only, isolated transactions, synthetic accounts."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.core.database import get_db
from app.core.security import password_hash


@pytest.fixture(scope="session")
def database_urls():
    application_url = os.environ.get("TEST_DATABASE_URL")
    owner_url = os.environ.get("ADMIN_DATABASE_URL")
    if not application_url or not owner_url:
        pytest.skip("S1 needs TEST_DATABASE_URL and ADMIN_DATABASE_URL for an isolated migrated PostgreSQL database")
    application, owner = make_url(application_url), make_url(owner_url)
    if application.get_backend_name() != "postgresql" or owner.get_backend_name() != "postgresql":
        pytest.fail("S1 integration tests require PostgreSQL; SQLite is not supported")
    if (application.host, application.port, application.database) != (owner.host, owner.port, owner.database):
        pytest.fail("Test application and migration-owner URLs must address the same isolated database")
    if "test" not in (application.database or "").lower():
        pytest.fail("Use a dedicated database with 'test' in its name; these tests do not run against the demo volume")
    return application_url, owner_url


@pytest.fixture(scope="session")
def owner_engine(database_urls):
    engine = create_engine(database_urls[1], pool_pre_ping=True, connect_args={"connect_timeout": 5}, hide_parameters=True)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='risk_school' AND table_type='BASE TABLE'")).scalar_one() == 13, "Run Alembic against the clean test database first"
    yield engine
    engine.dispose()


@pytest.fixture
def db(owner_engine):
    """Each test and all its HTTP requests share one rollback-only outer transaction."""
    with owner_engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


@pytest.fixture(scope="session")
def synthetic_password():
    return "S1-fixture-only-" + uuid4().hex


@pytest.fixture(scope="session")
def synthetic_password_hash(synthetic_password):
    return password_hash(synthetic_password)


@pytest.fixture
def context(db, synthetic_password, synthetic_password_hash):
    accounts = {}
    for role in ("ADMIN", "TUTOR", "DIRECTOR", "RESEARCHER"):
        account = {
            "id": uuid4(),
            "email": f"s1-{role.lower()}-{uuid4().hex}@example.com",
            "display_name": f"Cuenta sintética S1 {role}",
            "role": role,
            "password": synthetic_password,
        }
        db.execute(text("INSERT INTO risk_school.app_users (id,email,display_name,password_hash,role) VALUES (:id,:email,:display_name,:password_hash,:role)"), {**account, "password_hash": synthetic_password_hash})
        accounts[role] = account
    periods = {}
    for key, year, origin in (("demo", 2026, "DEMO"), ("other_year", 2027, "DEMO"), ("real", 2026, "REAL")):
        period = {"id": uuid4(), "code": f"S1-{key}-{uuid4().hex[:12]}", "school_year": year, "data_origin": origin}
        db.execute(text("INSERT INTO risk_school.academic_periods (id,code,school_year,start_date,end_date,data_origin) VALUES (:id,:code,:school_year,:start_date,:end_date,:data_origin)"), {**period, "start_date": date(year, 1, 1), "end_date": date(year, 12, 31)})
        periods[key] = period
    sections = []
    # Distinct codes make fixture independent of an explicitly seeded database.
    code = "S1-" + uuid4().hex[:8]
    for grade, year, tutor in ((1, 2026, accounts["TUTOR"]["id"]), (2, 2026, None), (1, 2027, None)):
        section = {"id": uuid4(), "code": code, "grade": grade, "school_year": year, "tutor_id": tutor}
        db.execute(text("INSERT INTO risk_school.grade_sections (id,code,grade,school_year,tutor_id) VALUES (:id,:code,:grade,:school_year,:tutor_id)"), section)
        sections.append(section)
    return {"accounts": accounts, "periods": periods, "sections": sections}


@pytest.fixture
def app(db, database_urls, monkeypatch):
    # app.main exports the configured ASGI instance. Establish a test-only environment
    # before its first import, including removal of any demo file overrides.
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_urls[0])
    monkeypatch.setenv("CSRF_SECRET", "s1-test-only-CSRF-secret-at-least-32-characters")
    monkeypatch.delenv("DATABASE_URL_FILE", raising=False)
    monkeypatch.delenv("CSRF_SECRET_FILE", raising=False)
    from app.main import create_app

    settings = Settings(
        app_env="test",
        database_url=database_urls[0],
        database_url_file=None,
        csrf_secret="s1-test-only-CSRF-secret-at-least-32-characters",
        csrf_secret_file=None,
        allowed_origins="http://testserver,http://localhost:5173",
        session_cookie_secure=False,
    )
    application = create_app(settings)

    def transactional_session():
        with Session(bind=db, join_transaction_mode="create_savepoint") as session:
            yield session

    application.dependency_overrides[get_db] = transactional_session
    yield application
    application.dependency_overrides.clear()
    application.state.database.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def login(client, context):
    def authenticate(role="ADMIN", **extra):
        account = context["accounts"][role]
        response = client.post("/api/v1/auth/login", json={"email": account["email"], "password": account["password"], **extra}, headers={"Origin": "http://testserver"})
        assert response.status_code == 200, response.json()
        return response

    return authenticate
