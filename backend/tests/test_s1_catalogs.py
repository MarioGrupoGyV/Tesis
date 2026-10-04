"""S1 catalogs prove role and section scope from the server session."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from test_s1_sessions import API, assert_error


@pytest.mark.parametrize("role", ("ADMIN", "DIRECTOR"))
def test_admin_and_director_read_demo_year_catalog(client, login, context, role):
    login(role)
    periods = client.get(f"{API}/periods")
    assert periods.status_code == 200
    rows = periods.json()
    assert str(context["periods"]["demo"]["id"]) in {row["id"] for row in rows}
    assert str(context["periods"]["other_year"]["id"]) in {row["id"] for row in rows}
    assert all(row["data_origin"] == "DEMO" for row in rows)
    for row in rows:
        assert set(row) == {"id", "code", "school_year", "start_date", "end_date", "data_origin", "is_locked"}
        UUID(row["id"])
        assert 2000 <= row["school_year"] <= 2100
        assert date.fromisoformat(row["start_date"]) < date.fromisoformat(row["end_date"])
    sections = client.get(f"{API}/sections", params={"period_id": str(context["periods"]["demo"]["id"])})
    assert sections.status_code == 200
    own, other, next_year = context["sections"]
    visible = {row["id"] for row in sections.json()}
    assert str(own["id"]) in visible and str(other["id"]) in visible
    assert str(next_year["id"]) not in visible
    for row in sections.json():
        assert set(row) == {"id", "code", "grade", "school_year", "tutor_id"}
        assert row["school_year"] == 2026
        assert 1 <= row["grade"] <= 5
        if row["tutor_id"] is not None:
            UUID(row["tutor_id"])


def test_tutor_only_assigned_sections_and_years_even_with_browser_role(client, login, context):
    login("TUTOR")
    periods = client.get(f"{API}/periods", headers={"X-Role": "ADMIN"}, params={"role": "ADMIN"})
    assert periods.status_code == 200
    assert all(row["school_year"] == 2026 and row["data_origin"] == "DEMO" for row in periods.json())
    sections = client.get(f"{API}/sections", params={"period_id": str(context["periods"]["demo"]["id"]), "role": "ADMIN"}, headers={"X-Role": "ADMIN"})
    assert sections.status_code == 200
    assert {row["id"] for row in sections.json()} == {str(context["sections"][0]["id"])}
    assert all(row["tutor_id"] == str(context["accounts"]["TUTOR"]["id"]) for row in sections.json())
    assert client.get(f"{API}/auth/me", headers={"X-Role": "ADMIN"}).json()["role"] == "TUTOR"


def test_tutor_without_assigned_year_cannot_read_that_catalog(client, login, context):
    login("TUTOR")
    response = client.get(f"{API}/sections", params={"period_id": str(context["periods"]["other_year"]["id"])})
    assert_error(response, 403)


def test_researcher_has_own_session_but_no_operational_catalog(client, login, context):
    response = login("RESEARCHER")
    assert response.json()["user"]["role"] == "RESEARCHER"
    assert client.get(f"{API}/auth/me").status_code == 200
    assert client.get(f"{API}/auth/csrf").status_code == 200
    assert_error(client.get(f"{API}/periods"), 403)
    assert_error(client.get(f"{API}/sections", params={"period_id": str(context["periods"]["demo"]["id"])}), 403)
    # Authorization precedes the REAL guard, so inaccessible records do not leak origin.
    assert_error(client.get(f"{API}/sections", params={"period_id": str(context["periods"]["real"]["id"])}), 403)
    assert client.post(f"{API}/auth/logout", headers={"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf_token"]}).status_code == 204


@pytest.mark.parametrize("role", ("ADMIN", "DIRECTOR", "TUTOR"))
def test_real_period_is_blocked(client, login, context, role):
    login(role)
    response = client.get(f"{API}/sections", params={"period_id": str(context["periods"]["real"]["id"])})
    assert_error(response, 422, "REAL_MODE_NOT_READY")


@pytest.mark.parametrize("period_id", (None, "not-a-uuid"))
def test_sections_validates_required_uuid(client, login, period_id):
    login()
    params = {} if period_id is None else {"period_id": period_id}
    assert_error(client.get(f"{API}/sections", params=params), 422)


def test_unknown_period_does_not_fall_back_to_full_catalog(client, login):
    login()
    assert_error(client.get(f"{API}/sections", params={"period_id": str(uuid4())}), 404)


def test_locked_period_still_permits_session_operations(client, login, context, db):
    db.execute(text("UPDATE risk_school.academic_periods SET is_locked=true WHERE id=:id"), context["periods"]["demo"])
    response = login()
    periods = client.get(f"{API}/periods").json()
    assert next(row for row in periods if row["id"] == str(context["periods"]["demo"]["id"]))["is_locked"] is True
    assert client.post(f"{API}/auth/logout", headers={"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf_token"]}).status_code == 204
