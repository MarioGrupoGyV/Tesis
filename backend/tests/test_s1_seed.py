"""An explicit synthetic seed is idempotent and refuses to overwrite accounts."""

from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.seed_demo import DemoCredentials, SeedError, seed_demo, seed_id


@pytest.fixture
def demo_credentials(synthetic_password):
    return DemoCredentials.model_validate({name: {"email": f"s1-seed-{name}-{uuid4().hex}@example.com", "password": synthetic_password} for name in ("admin", "tutor", "director")})


def test_explicit_seed_creates_only_context_and_is_idempotent(db, demo_credentials):
    assert db.execute(text("SELECT count(*) FROM risk_school.app_users WHERE id=:id"), {"id": seed_id("user:admin")}).scalar_one() == 0, "Seed tests require a clean isolated test database"
    with Session(bind=db, join_transaction_mode="create_savepoint") as session:
        first = seed_demo(session, demo_credentials)
        session.commit()
        assert first == {"data_origin": "DEMO", "users_created": 3, "periods_created": 1, "sections_created": 2}
        before = db.execute(text("SELECT id,password_hash,created_at FROM risk_school.app_users ORDER BY id")).all()
        audit_count = db.execute(text("SELECT count(*) FROM risk_school.audit_events")).scalar_one()
        second = seed_demo(session, demo_credentials)
        session.commit()
        assert second == {"data_origin": "DEMO", "users_created": 0, "periods_created": 0, "sections_created": 0}
        assert db.execute(text("SELECT id,password_hash,created_at FROM risk_school.app_users ORDER BY id")).all() == before
        assert db.execute(text("SELECT count(*) FROM risk_school.audit_events")).scalar_one() == audit_count
        assert db.execute(text("SELECT grade,code FROM risk_school.grade_sections ORDER BY grade")).all() == [(1, "A"), (2, "A")]
        assert db.execute(text("SELECT DISTINCT data_origin FROM risk_school.academic_periods")).scalars().all() == ["DEMO"]
        for table in ("students", "enrollments", "academic_snapshots", "model_versions", "predictions", "alerts", "interventions", "import_batches"):
            assert db.execute(text(f"SELECT count(*) FROM risk_school.{table}")).scalar_one() == 0


def test_existing_seed_credentials_are_not_silently_reset(db, demo_credentials):
    with Session(bind=db, join_transaction_mode="create_savepoint") as session:
        seed_demo(session, demo_credentials)
        session.commit()
        before = db.execute(text("SELECT password_hash FROM risk_school.app_users WHERE id=:id"), {"id": seed_id("user:admin")}).scalar_one()
        replacement = demo_credentials.model_copy(update={"admin": demo_credentials.admin.model_copy(update={"password": SecretStr("new-synthetic-password-never-reset")})})
        with pytest.raises(SeedError):
            seed_demo(session, replacement)
        session.rollback()
        assert db.execute(text("SELECT password_hash FROM risk_school.app_users WHERE id=:id"), {"id": seed_id("user:admin")}).scalar_one() == before


@pytest.mark.parametrize("override", ({"data_origin": "REAL"}, {"real_mode_enabled": True}))
def test_configuration_cannot_enable_institutional_processing(override):
    with pytest.raises(ValidationError) as caught:
        Settings(app_env="test", database_url="postgresql+psycopg://s1_fixture:unused@localhost/risk_school_s1_test", database_url_file=None, csrf_secret="s1-test-only-CSRF-secret-at-least-32-characters", csrf_secret_file=None, allowed_origins="http://testserver", session_cookie_secure=False, **override)
    if "data_origin" in override:
        assert "data_origin" in {error["loc"][0] for error in caught.value.errors() if error["loc"]}
    else:
        assert any("REAL_MODE_NOT_READY" in error["msg"] for error in caught.value.errors())
