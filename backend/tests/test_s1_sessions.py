"""Contract 0.1.1 session controls, exercised against migrated PostgreSQL."""

from datetime import datetime, timezone
import hashlib
import hmac
import re
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import get_db

API = "/api/v1"


def assert_error(response, status, code=None):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details", "request_id"}
    assert isinstance(body["code"], str) and body["code"]
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["details"], list)
    UUID(body["request_id"])
    for detail in body["details"]:
        assert "message" in detail
        assert set(detail) <= {"field", "row", "message"}
    if code:
        assert body["code"] == code
    return body


def test_health_contract(client):
    for endpoint in ("live", "ready"):
        response = client.get(f"{API}/health/{endpoint}")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_ready_reports_unavailable_without_internal_details(client, app, monkeypatch):
    def disconnected():
        raise SQLAlchemyError("synthetic connection failure containing private infrastructure details")

    monkeypatch.setattr(app.state.database.engine, "connect", disconnected)
    ready = client.get(f"{API}/health/ready")
    assert ready.status_code == 503 and ready.json() == {"status": "unavailable"}
    assert client.get(f"{API}/health/live").json() == {"status": "ok"}


@pytest.mark.parametrize("path", ("auth/me", "auth/csrf", "periods", "sections?period_id=00000000-0000-0000-0000-000000000001"))
def test_session_required(client, path):
    assert_error(client.get(f"{API}/{path}"), 401)


@pytest.mark.parametrize("origin", (None, "https://untrusted.example.com", "http://testserver.evil.example.com", "null"))
def test_login_requires_exact_allowed_origin(client, context, origin):
    account = context["accounts"]["ADMIN"]
    headers = {} if origin is None else {"Origin": origin}
    response = client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, headers=headers)
    assert_error(response, 403)
    assert "session=" not in response.headers.get("set-cookie", "")


def test_invalid_credentials_do_not_create_session(client, context, db):
    account = context["accounts"]["ADMIN"]
    response = client.post(f"{API}/auth/login", json={"email": account["email"], "password": "incorrect-fixture-password"}, headers={"Origin": "http://testserver"})
    assert_error(response, 401)
    assert db.execute(text("SELECT count(*) FROM risk_school.user_sessions WHERE user_id=:id"), account).scalar_one() == 0


def test_missing_account_has_same_public_error(client, context):
    known = client.post(f"{API}/auth/login", json={"email": context["accounts"]["ADMIN"]["email"], "password": "incorrect-fixture-password"}, headers={"Origin": "http://testserver"})
    unknown = client.post(f"{API}/auth/login", json={"email": "unknown-s1-fixture@example.com", "password": "incorrect-fixture-password"}, headers={"Origin": "http://testserver"})
    a, b = assert_error(known, 401), assert_error(unknown, 401)
    assert (a["code"], a["message"], a["details"]) == (b["code"], b["message"], b["details"])


def test_login_rate_limit(client, context, app):
    account = context["accounts"]["ADMIN"]
    for _ in range(app.state.settings.login_attempt_limit):
        response = client.post(f"{API}/auth/login", json={"email": account["email"], "password": "wrong"}, headers={"Origin": "http://testserver"})
        assert_error(response, 401)
    assert_error(client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"Origin": "http://testserver"}), 429)
    assert "session" not in client.cookies


def test_login_ip_limit_survives_changing_email_and_forwarded_headers(client, context, app):
    for attempt in range(app.state.settings.login_attempt_limit):
        response = client.post(f"{API}/auth/login", json={"email": f"s1-unknown-{attempt}@example.com", "password": "wrong"}, headers={"Origin": "http://testserver", "X-Forwarded-For": f"192.0.2.{attempt + 1}"})
        assert_error(response, 401)
    account = context["accounts"]["ADMIN"]
    response = client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"Origin": "http://testserver", "X-Forwarded-For": "192.0.2.250"})
    assert_error(response, 429)
    assert int(response.headers["retry-after"]) > 0


def test_login_email_limit_survives_changing_client_ip(app, context):
    account = context["accounts"]["ADMIN"]
    for attempt in range(app.state.settings.login_attempt_limit):
        with TestClient(app, client=(f"192.0.2.{attempt + 1}", 50000)) as other_client:
            response = other_client.post(f"{API}/auth/login", json={"email": account["email"], "password": "wrong"}, headers={"Origin": "http://testserver"})
            assert_error(response, 401)
    with TestClient(app, client=("192.0.2.250", 50000)) as final_client:
        response = final_client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"Origin": "http://testserver"})
        assert_error(response, 429)


def test_browser_cannot_choose_role_at_login(client, context):
    account = context["accounts"]["TUTOR"]
    response = client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"], "role": "ADMIN"}, headers={"Origin": "http://testserver"})
    assert_error(response, 422)


def test_login_public_contract_cookie_and_only_digests(client, login, context, db, app):
    response = login()
    body = response.json()
    assert set(body) == {"user", "csrf_token", "expires_at"}
    assert set(body["user"]) == {"id", "display_name", "role"}
    UUID(body["user"]["id"])
    assert body["user"]["role"] == "ADMIN"
    assert body["expires_at"].endswith("Z")
    assert datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert "secure" not in cookie  # Local HTTP test environment, HTTPS covered separately.
    raw_token, csrf = client.cookies["session"], body["csrf_token"]
    row = db.execute(text("SELECT token_digest,csrf_digest FROM risk_school.user_sessions WHERE user_id=:id"), context["accounts"]["ADMIN"]).mappings().one()
    assert row["token_digest"] == hashlib.sha256(raw_token.encode()).hexdigest()
    assert row["csrf_digest"] == hashlib.sha256(csrf.encode()).hexdigest()
    assert csrf == hmac.new(app.state.settings.csrf_secret.get_secret_value().encode(), ("csrf:v1:" + raw_token).encode(), hashlib.sha256).hexdigest()
    assert raw_token not in row.values() and csrf not in row.values()
    assert re.fullmatch("[0-9a-f]{64}", row["token_digest"])
    assert "token" not in body and "session" not in body


def test_https_cookie_is_secure(app, context, database_urls):
    from app.main import create_app

    settings = Settings(app_env="test", database_url=database_urls[0], database_url_file=None, csrf_secret="s1-test-only-CSRF-secret-at-least-32-characters", csrf_secret_file=None, allowed_origins="https://testserver", session_cookie_secure=True)
    https_app = create_app(settings)
    https_app.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    account = context["accounts"]["ADMIN"]
    try:
        with TestClient(https_app, base_url="https://testserver") as https_client:
            response = https_client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"Origin": "https://testserver"})
            assert response.status_code == 200
            attributes = response.headers["set-cookie"].lower().split(";")
            assert "secure" in [part.strip() for part in attributes]
            assert "httponly" in [part.strip() for part in attributes]
            assert "samesite=lax" in [part.strip() for part in attributes]
            assert https_client.get(f"{API}/auth/me").status_code == 200
    finally:
        https_app.state.database.engine.dispose()


def test_me_and_csrf_are_session_bound(client, login, context):
    first = login("TUTOR").json()
    me = client.get(f"{API}/auth/me")
    assert me.status_code == 200 and me.json() == first["user"]
    recovered = client.get(f"{API}/auth/csrf")
    assert recovered.status_code == 200
    assert recovered.json() == {"csrf_token": first["csrf_token"]}
    second = login("TUTOR").json()
    assert second["csrf_token"] != first["csrf_token"]
    assert client.get(f"{API}/auth/csrf").json()["csrf_token"] == second["csrf_token"]


@pytest.mark.parametrize("csrf", (None, "incorrect-token"))
def test_logout_rejects_missing_or_invalid_csrf(client, login, csrf):
    login()
    headers = {"Origin": "http://testserver"}
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    assert_error(client.post(f"{API}/auth/logout", headers=headers), 403)
    assert client.get(f"{API}/auth/me").status_code == 200


def test_csrf_from_a_different_session_is_rejected(client, login):
    first = login().json()["csrf_token"]
    login()
    assert_error(client.post(f"{API}/auth/logout", headers={"Origin": "http://testserver", "X-CSRF-Token": first}), 403)


def test_logout_revokes_server_session_even_with_replayed_cookie(client, login, db):
    csrf = login().json()["csrf_token"]
    original_cookie = client.cookies["session"]
    digest = hashlib.sha256(original_cookie.encode()).hexdigest()
    response = client.post(f"{API}/auth/logout", headers={"Origin": "http://testserver", "X-CSRF-Token": csrf})
    assert response.status_code == 204 and response.content == b""
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert db.execute(text("SELECT revoked_at FROM risk_school.user_sessions WHERE token_digest=:digest"), {"digest": digest}).scalar_one() is not None
    client.cookies.set("session", original_cookie)
    assert_error(client.get(f"{API}/auth/me"), 401)
    assert_error(client.get(f"{API}/auth/csrf"), 401)


def test_expired_session_is_rejected(client, login, db):
    login()
    digest = hashlib.sha256(client.cookies["session"].encode()).hexdigest()
    db.execute(text("UPDATE risk_school.user_sessions SET created_at=now()-interval '2 seconds', expires_at=now()-interval '1 second' WHERE token_digest=:digest"), {"digest": digest})
    assert_error(client.get(f"{API}/auth/me"), 401)


def test_deactivated_user_loses_existing_session(client, login, context, db):
    login()
    db.execute(text("UPDATE risk_school.app_users SET is_active=false WHERE id=:id"), context["accounts"]["ADMIN"])
    assert_error(client.get(f"{API}/auth/me"), 401)


def test_inactive_user_cannot_login(client, context, db):
    account = context["accounts"]["ADMIN"]
    db.execute(text("UPDATE risk_school.app_users SET is_active=false WHERE id=:id"), account)
    response = client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"Origin": "http://testserver"})
    assert_error(response, 401)


def test_current_server_role_overrides_browser_claims(client, login, context, db):
    login("TUTOR")
    db.execute(text("UPDATE risk_school.app_users SET role='RESEARCHER' WHERE id=:id"), context["accounts"]["TUTOR"])
    me = client.get(f"{API}/auth/me", headers={"X-Role": "ADMIN"})
    assert me.status_code == 200 and me.json()["role"] == "RESEARCHER"
    assert_error(client.get(f"{API}/periods", headers={"X-Role": "ADMIN"}), 403)


def test_csrf_recovery_rejects_a_corrupted_stored_digest(client, login, db):
    login()
    digest = hashlib.sha256(client.cookies["session"].encode()).hexdigest()
    db.execute(text("UPDATE risk_school.user_sessions SET csrf_digest=repeat('a',64) WHERE token_digest=:digest"), {"digest": digest})
    assert_error(client.get(f"{API}/auth/csrf"), 401)


def test_invalid_session_token_and_forged_request_id(client):
    client.cookies.set("session", "synthetic-forged-token")
    body = assert_error(client.get(f"{API}/auth/me", headers={"X-Request-ID": "not-a-uuid"}), 401)
    assert body["request_id"] != "not-a-uuid"


def test_no_secrets_in_audit_payload(client, login, db, context):
    response = login()
    token = client.cookies["session"]
    csrf = response.json()["csrf_token"]
    payloads = db.execute(text("SELECT payload::text FROM risk_school.audit_events WHERE actor_id=:id"), context["accounts"]["ADMIN"]).scalars().all()
    assert payloads, "A successful login must record its audit event in the same transaction"
    for payload in payloads:
        assert token not in payload and csrf not in payload
        assert context["accounts"]["ADMIN"]["password"] not in payload


def test_login_and_audit_roll_back_together_on_audit_failure(client, context, db, monkeypatch):
    from app.services import auth

    def audit_unavailable(**kwargs):
        raise SQLAlchemyError("synthetic audit failure")

    monkeypatch.setattr(auth, "AuditEvent", audit_unavailable)
    account = context["accounts"]["ADMIN"]
    response = client.post(f"{API}/auth/login", json={"email": account["email"], "password": account["password"]}, headers={"Origin": "http://testserver"})
    assert_error(response, 503)
    assert "session=" not in response.headers.get("set-cookie", "")
    assert db.execute(text("SELECT count(*) FROM risk_school.user_sessions WHERE user_id=:id"), account).scalar_one() == 0


def test_logout_revocation_rolls_back_if_audit_fails(client, login, db, monkeypatch):
    from app.services import auth

    csrf = login().json()["csrf_token"]
    digest = hashlib.sha256(client.cookies["session"].encode()).hexdigest()

    def audit_unavailable(**kwargs):
        raise SQLAlchemyError("synthetic audit failure")

    monkeypatch.setattr(auth, "AuditEvent", audit_unavailable)
    assert_error(client.post(f"{API}/auth/logout", headers={"Origin": "http://testserver", "X-CSRF-Token": csrf}), 503)
    assert db.execute(text("SELECT revoked_at FROM risk_school.user_sessions WHERE token_digest=:digest"), {"digest": digest}).scalar_one() is None
    assert client.get(f"{API}/auth/me").status_code == 200
