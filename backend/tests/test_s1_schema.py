"""Migration structure and real PostgreSQL privilege/immutable-evidence controls."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

TABLES = {
    "app_users", "user_sessions", "academic_periods", "grade_sections", "students",
    "enrollments", "import_batches", "academic_snapshots", "model_versions",
    "predictions", "alerts", "interventions", "audit_events",
    "synthetic_studies",
}


def assert_sqlstate(db, statement, values, sqlstate):
    savepoint = db.begin_nested()
    try:
        with pytest.raises(DBAPIError) as caught:
            db.execute(text(statement), values)
        assert caught.value.orig.sqlstate == sqlstate
    finally:
        savepoint.rollback()


def test_migration_has_design_tables_and_s31_provenance_registry(db):
    inspector = inspect(db)
    assert set(inspector.get_table_names(schema="risk_school")) == TABLES
    assert "school_year" in {row["name"] for row in inspector.get_columns("academic_periods", schema="risk_school")}
    batches = {row["name"] for row in inspector.get_columns("import_batches", schema="risk_school")}
    assert {"planned_students", "planned_enrollments", "planned_snapshots", "preview_version", "preview_state"} <= batches
    snapshots = {row["name"] for row in inspector.get_columns("academic_snapshots", schema="risk_school")}
    assert {"supersedes_id", "window_start", "cutoff_at", "available_at", "target_date"} <= snapshots
    sessions = {row["name"] for row in inspector.get_columns("user_sessions", schema="risk_school")}
    assert {"token_digest", "csrf_digest", "expires_at", "revoked_at"} <= sessions
    assert not {"token", "session_token", "csrf_token", "password"} & sessions


def test_critical_unique_indexes_and_composite_origin_foreign_keys(db):
    inspector = inspect(db)
    alert_indexes = {index["name"]: index for index in inspector.get_indexes("alerts", schema="risk_school")}
    assert alert_indexes["ux_active_alert_enrollment"]["unique"]
    assert "postgresql_where" in alert_indexes["ux_active_alert_enrollment"]["dialect_options"]
    model_indexes = {index["name"]: index for index in inspector.get_indexes("model_versions", schema="risk_school")}
    assert model_indexes["ux_active_model_origin"]["unique"]
    prediction_unique = [constraint["column_names"] for constraint in inspector.get_unique_constraints("predictions", schema="risk_school")]
    assert ["snapshot_id", "model_id"] in prediction_unique
    for table, minimum in (("enrollments", 2), ("academic_snapshots", 3), ("predictions", 2), ("alerts", 1), ("interventions", 2)):
        origin_fks = [fk for fk in inspector.get_foreign_keys(table, schema="risk_school") if "data_origin" in fk["constrained_columns"]]
        assert len(origin_fks) >= minimum


def test_session_tokens_reject_non_digest_storage(db, context):
    values = {"id": uuid4(), "user_id": context["accounts"]["ADMIN"]["id"]}
    assert_sqlstate(db, "INSERT INTO risk_school.user_sessions (id,user_id,token_digest,csrf_digest,expires_at) VALUES (:id,:user_id,'plaintext-session-token',repeat('a',64),now()+interval '8 hours')", values, "23514")


def test_grade_and_code_uniqueness_allows_1a_and_2a(db, context):
    # Same section code is valid across grades, but the complete tuple cannot repeat.
    first, second, _ = context["sections"]
    assert first["code"] == second["code"] and {first["grade"], second["grade"]} == {1, 2}
    assert_sqlstate(db, "INSERT INTO risk_school.grade_sections (id,code,grade,school_year) VALUES (:id,:code,:grade,:school_year)", {**first, "id": uuid4()}, "23505")


def test_database_checks_year_grade_and_period_order(db):
    for year in (1999, 2101):
        assert_sqlstate(db, "INSERT INTO risk_school.academic_periods (code,school_year,start_date,end_date,data_origin) VALUES (:code,:year,'2026-01-01','2026-12-31','REAL')", {"code": "synthetic-" + uuid4().hex, "year": year}, "23514")
    assert_sqlstate(db, "INSERT INTO risk_school.grade_sections (code,grade,school_year) VALUES ('synthetic',6,2026)", {}, "23514")
    assert_sqlstate(db, "INSERT INTO risk_school.academic_periods (code,school_year,start_date,end_date,data_origin) VALUES (:code,2026,'2026-12-31','2026-01-01','REAL')", {"code": "synthetic-" + uuid4().hex}, "23514")


def test_immutable_evidence_triggers_are_installed(db):
    triggers = set(db.execute(text("SELECT tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='risk_school' AND NOT t.tgisinternal")).scalars())
    assert {"snapshots_immutable", "predictions_immutable", "audit_immutable", "snapshot_period_guard", "alert_change_guard", "intervention_change_guard"} <= triggers


def test_processing_migration_preserves_institutional_block_and_historical_origins(db):
    # S3.1 replaces the total block with an explicit REAL/SYNTHETIC write guard.
    # DEMO remains a historical value, never an accepted new processing context.
    assert db.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='processing_origin' AND convalidated")) == 9
    assert_sqlstate(db, "INSERT INTO risk_school.academic_periods(code,school_year,start_date,end_date,data_origin) VALUES (:code,2026,'2026-01-01','2026-12-31','DEMO')", {'code':uuid4().hex}, '23514')
    assert db.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname='synthetic_only_active_model'")) == 1
    assert db.scalar(text("SELECT count(*) FROM pg_constraint WHERE conname IN ('model_activation_pending','demo_only_active_model','institutional_origin')")) == 0


@pytest.mark.parametrize("mutation", ("UPDATE risk_school.audit_events SET action='changed' WHERE id=:id", "DELETE FROM risk_school.audit_events WHERE id=:id"))
def test_audit_cannot_be_overwritten_even_by_migration_owner(db, context, mutation):
    db.execute(text("RESET ROLE"))
    values = {"id": uuid4(), "actor_id": context["accounts"]["ADMIN"]["id"], "request_id": uuid4()}
    db.execute(text("INSERT INTO risk_school.audit_events (id,actor_id,entity_type,action,request_id) VALUES (:id,:actor_id,'S1_FIXTURE','SYNTHETIC_TEST',:request_id)"), values)
    assert_sqlstate(db, mutation, values, "55000")


def test_application_role_cannot_use_ddl_or_modify_evidence(database_urls):
    engine = create_engine(database_urls[0], connect_args={"connect_timeout": 5}, hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT has_schema_privilege(current_user,'risk_school','CREATE')")).scalar_one() is False
            assert connection.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")).scalar_one() is False
            for table in ("academic_snapshots", "predictions", "audit_events"):
                for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
                    assert connection.execute(text("SELECT has_table_privilege(current_user,:table,:privilege)"), {"table": f"risk_school.{table}", "privilege": privilege}).scalar_one() is False
            assert_sqlstate(connection, "CREATE TABLE risk_school.s1_ddl_probe (id integer)", {}, "42501")
            assert_sqlstate(connection, "UPDATE risk_school.audit_events SET action='changed' WHERE false", {}, "42501")
            assert_sqlstate(connection, "DELETE FROM risk_school.audit_events WHERE false", {}, "42501")
    finally:
        engine.dispose()
