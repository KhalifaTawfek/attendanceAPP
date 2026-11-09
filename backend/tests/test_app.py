import io
from datetime import UTC, datetime, timedelta

import pytest
from openpyxl import load_workbook
from pydantic import ValidationError

from app.config import Settings
from tests.conftest import auth_headers, png_bytes


def iso(dt: datetime) -> str:
    return dt.isoformat()


def make_event(client, admin, start_offset_min=-5, duration_min=60, **extra):
    now = datetime.now(UTC)
    body = {
        "title": "Standup",
        "location": "Room 1",
        "starts_at": iso(now + timedelta(minutes=start_offset_min)),
        "ends_at": iso(now + timedelta(minutes=start_offset_min + duration_min)),
        **extra,
    }
    r = client.post("/api/events", headers=admin, json=body)
    assert r.status_code == 201, r.text
    return r.json()[0]


def submit(client, headers, event_id, declaration="true", photo=None):
    return client.post(
        "/api/attendances",
        headers=headers,
        data={"event_id": event_id, "activity_summary": "Attended the standup",
              "declaration": declaration, "location_note": "Desk 4"},
        files={"photo": ("me.png", photo if photo is not None else png_bytes(), "image/png")},
    )


def test_health_and_metrics(client):
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/metrics")
    assert r.status_code == 200 and "http_requests_total" in r.text


def test_production_rejects_default_credentials():
    with pytest.raises(ValidationError):
        Settings(app_env="production", jwt_secret="change-me-in-production",
                 admin_password="admin12345",
                 database_url="postgresql+psycopg://attendance:attendance@localhost/attendance")


def test_auth_required_and_admin_only(client, user):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/admin/users", headers=user).status_code == 403
    assert client.get("/api/auth/me", headers=user).json()["email"] == "jane@test.io"


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"email": "admin@test.io", "password": "nope"})
    assert r.status_code == 401


def test_password_byte_limit_and_token_revocation(client, admin, user):
    long_password = "A" * 72 + "OriginalSuffix"
    r = client.post("/api/admin/users", headers=admin, json={
        "email": "long@test.io", "full_name": "Long", "password": long_password})
    assert r.status_code == 422
    assert client.post("/api/auth/login", json={
        "email": "jane@test.io", "password": long_password}).status_code == 422
    assert client.post("/api/admin/users", headers=admin, json={
        "email": "unicode@test.io", "full_name": "Unicode",
        "password": "é" * 37}).status_code == 422  # 74 UTF-8 bytes

    changed = client.post("/api/auth/change-password", headers=user, json={
        "current_password": "janepass123", "new_password": "newpass123"})
    assert changed.status_code == 204
    assert client.get("/api/auth/me", headers=user).status_code == 401
    new_token = auth_headers(client, "jane@test.io", "newpass123")
    assert client.post("/api/auth/logout", headers=new_token).status_code == 204
    assert client.get("/api/auth/me", headers=new_token).status_code == 401

    again = auth_headers(client, "jane@test.io", "newpass123")
    uid = client.get("/api/auth/me", headers=again).json()["id"]
    assert client.patch(f"/api/admin/users/{uid}", headers=admin,
                        json={"password": "resetpass123"}).status_code == 200
    assert client.get("/api/auth/me", headers=again).status_code == 401


def test_self_registration_disabled_by_default(client):
    r = client.post("/api/auth/register", json={"email": "x@test.io", "full_name": "X", "password": "12345678"})
    assert r.status_code == 403


def test_user_and_event_lists_are_paginated(client, admin, user):
    client.post("/api/admin/users", headers=admin, json={
        "email": "bob@test.io", "full_name": "Bob", "password": "bobpass123"})
    first = client.get("/api/admin/users", headers=admin, params={"page_size": 1}).json()
    second = client.get("/api/admin/users", headers=admin, params={"page_size": 1, "page": 2}).json()
    assert len(first) == len(second) == 1
    assert first[0]["id"] != second[0]["id"]
    assert client.get("/api/admin/users", headers=admin,
                      params={"page_size": 201}).status_code == 422

    a = make_event(client, admin, title="First")
    b = make_event(client, admin, title="Second")
    page1 = client.get("/api/events", headers=admin,
                       params={"scope": "all", "page_size": 1}).json()
    page2 = client.get("/api/events", headers=admin,
                       params={"scope": "all", "page_size": 1, "page": 2}).json()
    assert {page1[0]["id"], page2[0]["id"]} == {a["id"], b["id"]}


def test_event_validation(client, admin):
    now = datetime.now(UTC)
    r = client.post("/api/events", headers=admin, json={
        "title": "Bad", "starts_at": iso(now), "ends_at": iso(now - timedelta(hours=1))})
    assert r.status_code == 422
    r = client.post("/api/events", headers=admin, json={
        "title": "Naive", "starts_at": "2026-01-01T10:00:00", "ends_at": "2026-01-01T11:00:00"})
    assert r.status_code == 422


def test_event_defaults(client, admin):
    ev = make_event(client, admin)
    opens = datetime.fromisoformat(ev["check_in_opens_at"])
    starts = datetime.fromisoformat(ev["starts_at"])
    assert starts - opens == timedelta(minutes=15)
    assert ev["late_after_minutes"] == 10


def test_full_attendance_flow(client, admin, user):
    ev = make_event(client, admin)
    events = client.get("/api/events", headers=user).json()
    assert events[0]["check_in_open"] is True and events[0]["my_attendance_status"] is None

    r = submit(client, user, ev["id"])
    assert r.status_code == 201, r.text
    att = r.json()
    assert att["status"] == "pending" and att["is_late"] is False

    # duplicate rejected
    assert submit(client, user, ev["id"]).status_code == 409

    # own photo visible, re-encoded as JPEG
    r = client.get(f"/api/attendances/{att['id']}/photo", headers=user)
    assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"

    # admin review
    r = client.patch(f"/api/admin/attendances/{att['id']}", headers=admin,
                     json={"status": "approved", "review_comment": "ok"})
    assert r.json()["status"] == "approved"
    assert client.get("/api/attendances/me", headers=user).json()[0]["status"] == "approved"

    stats = client.get("/api/admin/stats", headers=admin).json()
    assert stats["approved"] == 1 and stats["total_users"] == 1


def test_late_flag(client, admin, user):
    ev = make_event(client, admin, start_offset_min=-30)
    assert submit(client, user, ev["id"]).json()["is_late"] is True


def test_check_in_closed(client, admin, user):
    future = make_event(client, admin, start_offset_min=120)
    assert submit(client, user, future["id"]).status_code == 409


def test_declaration_required_and_bad_image(client, admin, user):
    ev = make_event(client, admin)
    assert submit(client, user, ev["id"], declaration="false").status_code == 422
    assert submit(client, user, ev["id"], photo=b"not an image").status_code == 422


def test_photo_privacy(client, admin, user):
    ev = make_event(client, admin)
    att = submit(client, user, ev["id"]).json()
    client.post("/api/admin/users", headers=admin,
                json={"email": "bob@test.io", "full_name": "Bob", "password": "bobpass123"})
    bob = auth_headers(client, "bob@test.io", "bobpass123")
    assert client.get(f"/api/attendances/{att['id']}/photo", headers=bob).status_code == 404
    assert client.get(f"/api/attendances/{att['id']}/photo", headers=admin).status_code == 200


def test_filters_absentees_and_export(client, admin, user):
    ev = make_event(client, admin)
    submit(client, user, ev["id"])
    client.post("/api/admin/users", headers=admin,
                json={"email": "bob@test.io", "full_name": "Bob", "password": "bobpass123"})

    page = client.get("/api/admin/attendances", headers=admin, params={"q": "jane", "status": "pending"}).json()
    assert page["total"] == 1
    assert client.get("/api/admin/attendances", headers=admin, params={"status": "approved"}).json()["total"] == 0

    absent = client.get(f"/api/admin/events/{ev['id']}/absentees", headers=admin).json()
    assert [u["email"] for u in absent] == ["bob@test.io"]

    csv_r = client.get("/api/admin/attendances/export", headers=admin, params={"format": "csv"})
    assert csv_r.status_code == 200 and "Jane Doe" in csv_r.text
    assert "attachment" in csv_r.headers["content-disposition"]

    x = client.get("/api/admin/attendances/export", headers=admin, params={"format": "xlsx"})
    ws = load_workbook(io.BytesIO(x.content)).active
    assert ws.max_row == 2 and ws["D2"].value == "Jane Doe"


def test_rejected_not_present_and_title_search_rates(client, admin, user):
    ev = make_event(client, admin, title="Physics seminar", start_offset_min=-30)
    att = submit(client, user, ev["id"]).json()
    client.patch(f"/api/admin/attendances/{att['id']}", headers=admin,
                 json={"status": "rejected"})
    absent = client.get(f"/api/admin/events/{ev['id']}/absentees", headers=admin).json()
    assert [u["email"] for u in absent] == ["jane@test.io"]
    stats = client.get("/api/admin/stats", headers=admin).json()
    assert next(e for e in stats["recent_events"] if e["id"] == ev["id"])["attendances"] == 0

    summary = client.get("/api/admin/attendances/summary", headers=admin,
                         params={"q": "Physics", "date_from": "2020-01-01T00:00:00Z"}).json()
    assert summary["events_in_scope"] == 1
    assert summary["avg_turnout"] == 0
    assert summary["per_event"][0]["count"] == 0
    assert client.get("/api/admin/attendances", headers=admin,
                      params={"date_from": "2020-01-01T00:00:00"}).status_code == 422


def test_spreadsheet_export_escapes_formulas(client, admin, user):
    ev = make_event(client, admin)
    r = client.post("/api/attendances", headers=user,
                    data={"event_id": ev["id"], "activity_summary": "=HYPERLINK(\"https://bad.test\")",
                          "declaration": "true", "location_note": "  @SUM(1,2)"},
                    files={"photo": ("me.png", png_bytes(), "image/png")})
    assert r.status_code == 201
    csv_r = client.get("/api/admin/attendances/export", headers=admin)
    assert "'=HYPERLINK" in csv_r.text
    assert "'@SUM" in csv_r.text
    x = client.get("/api/admin/attendances/export", headers=admin, params={"format": "xlsx"})
    ws = load_workbook(io.BytesIO(x.content)).active
    assert ws["J2"].value.startswith("'=")
    assert ws["K2"].value.startswith("'@")


def test_deactivated_user_cannot_login(client, admin, user):
    uid = client.get("/api/auth/me", headers=user).json()["id"]
    client.patch(f"/api/admin/users/{uid}", headers=admin, json={"is_active": False})
    assert client.get("/api/auth/me", headers=user).status_code == 401
    r = client.post("/api/auth/login", json={"email": "jane@test.io", "password": "janepass123"})
    assert r.status_code == 403


def test_status_and_role_changes_revoke_existing_tokens(client, admin, user):
    uid = client.get("/api/auth/me", headers=user).json()["id"]
    assert client.patch(f"/api/admin/users/{uid}", headers=admin,
                        json={"is_active": False}).status_code == 200
    assert client.patch(f"/api/admin/users/{uid}", headers=admin,
                        json={"is_active": True}).status_code == 200
    assert client.get("/api/auth/me", headers=user).status_code == 401
    fresh = auth_headers(client, "jane@test.io", "janepass123")
    assert client.patch(f"/api/admin/users/{uid}", headers=admin,
                        json={"role": "admin"}).status_code == 200
    assert client.get("/api/auth/me", headers=fresh).status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers(
        client, "jane@test.io", "janepass123")).json()["role"] == "admin"


def test_admin_cannot_deactivate_self(client, admin):
    me = client.get("/api/auth/me", headers=admin).json()
    assert client.patch(f"/api/admin/users/{me['id']}", headers=admin, json={"is_active": False}).status_code == 400
