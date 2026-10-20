from datetime import UTC, date, datetime, timedelta

from app.models import Frequency
from app.recurrence import expand
from tests.conftest import auth_headers
from tests.test_app import iso, make_event, submit


# --- recurrence expansion (pure) ----------------------------------------------
def test_weekly_weekdays_count():
    start = datetime(2026, 11, 2, 9, tzinfo=UTC)  # Monday
    out = expand(start, frequency=Frequency.weekly, weekdays=[0, 2, 4], count=5)
    assert [d.strftime("%a %d") for d in out] == ["Mon 02", "Wed 04", "Fri 06", "Mon 09", "Wed 11"]


def test_weekly_interval_until():
    start = datetime(2026, 11, 2, 9, tzinfo=UTC)
    out = expand(start, frequency=Frequency.weekly, interval=2, until=date(2026, 12, 1))
    assert [d.day for d in out] == [2, 16, 30]


def test_monthly_skips_missing_days():
    start = datetime(2027, 1, 31, 9, tzinfo=UTC)
    out = expand(start, frequency=Frequency.monthly, count=3)
    assert [d.strftime("%b") for d in out] == ["Jan", "Mar", "May"]


def test_daily_keeps_local_time_across_dst():
    # Europe/Bucharest leaves DST on 2026-10-25: 09:00 local is 06:00Z before, 07:00Z after.
    start = datetime(2026, 10, 24, 6, tzinfo=UTC)
    out = expand(start, frequency=Frequency.daily, count=3, timezone="Europe/Bucharest")
    assert [d.hour for d in out] == [6, 7, 7]


# --- API ------------------------------------------------------------------------
def test_create_recurring_series_and_scoped_edit_delete(client, admin):
    now = datetime.now(UTC)
    r = client.post("/api/events", headers=admin, json={
        "title": "Daily standup", "starts_at": iso(now + timedelta(hours=1)),
        "ends_at": iso(now + timedelta(hours=1, minutes=15)),
        "recurrence": {"frequency": "daily", "count": 5},
    })
    assert r.status_code == 201, r.text
    events = r.json()
    assert len(events) == 5 and len({e["series_id"] for e in events}) == 1
    assert events[0]["series"]["frequency"] == "daily"
    for e in events:  # check-in window replicated per occurrence
        lead = datetime.fromisoformat(e["starts_at"]) - datetime.fromisoformat(e["check_in_opens_at"])
        assert lead == timedelta(minutes=15)

    third = events[2]
    r = client.patch(f"/api/events/{third['id']}", headers=admin, params={"scope": "future"},
                     json={"title": "Standup v2"})
    assert [e["title"] for e in r.json()] == ["Standup v2"] * 3
    titles = [e["title"] for e in client.get("/api/events?scope=all", headers=admin).json()]
    assert titles.count("Standup v2") == 3 and titles.count("Daily standup") == 2

    # shifting the time on all occurrences moves each by the same delta
    new_start = datetime.fromisoformat(events[0]["starts_at"]) + timedelta(minutes=30)
    r = client.patch(f"/api/events/{events[0]['id']}", headers=admin, params={"scope": "all"},
                     json={"starts_at": iso(new_start), "ends_at": iso(new_start + timedelta(minutes=15))})
    for before, after in zip(events, r.json()):
        shift = datetime.fromisoformat(after["starts_at"]) - datetime.fromisoformat(before["starts_at"])
        assert shift == timedelta(minutes=30)

    assert client.delete(f"/api/events/{third['id']}", headers=admin, params={"scope": "this"}).status_code == 204
    assert len(client.get("/api/events?scope=all", headers=admin).json()) == 4
    client.delete(f"/api/events/{events[0]['id']}", headers=admin, params={"scope": "all"})
    assert client.get("/api/events?scope=all", headers=admin).json() == []


def test_recurrence_requires_end(client, admin):
    now = datetime.now(UTC)
    r = client.post("/api/events", headers=admin, json={
        "title": "x", "starts_at": iso(now), "ends_at": iso(now + timedelta(hours=1)),
        "recurrence": {"frequency": "weekly"}})
    assert r.status_code == 422


def test_bad_timezone(client, admin):
    now = datetime.now(UTC)
    r = client.post("/api/events", headers=admin, json={
        "title": "x", "starts_at": iso(now), "ends_at": iso(now + timedelta(hours=1)),
        "recurrence": {"frequency": "daily", "count": 2, "timezone": "Mars/Olympus"}})
    assert r.status_code == 422


def test_groups_restrict_events(client, admin, user):
    client.post("/api/admin/users", headers=admin,
                json={"email": "bob@test.io", "full_name": "Bob", "password": "bobpass123"})
    bob = auth_headers(client, "bob@test.io", "bobpass123")
    users = {u["email"]: u["id"] for u in client.get("/api/admin/users", headers=admin).json()}

    g = client.post("/api/admin/groups", headers=admin,
                    json={"name": "Team A", "member_ids": [users["jane@test.io"]]})
    assert g.status_code == 201 and g.json()["member_ids"] == [users["jane@test.io"]]
    gid = g.json()["id"]
    assert client.post("/api/admin/groups", headers=admin, json={"name": "team a"}).status_code == 409

    ev = make_event(client, admin, group_ids=[gid])
    open_ev = make_event(client, admin)
    assert ev["groups"] == [{"id": gid, "name": "Team A"}]

    # Jane (member) sees both; Bob only the open one and cannot check in to the group event
    assert {e["id"] for e in client.get("/api/events", headers=user).json()} == {ev["id"], open_ev["id"]}
    assert {e["id"] for e in client.get("/api/events", headers=bob).json()} == {open_ev["id"]}
    assert client.get(f"/api/events/{ev['id']}", headers=bob).status_code == 404
    assert submit(client, bob, ev["id"]).status_code == 403
    assert submit(client, user, ev["id"]).status_code == 201

    # expected / absentees only count group members
    assert client.get(f"/api/admin/events/{ev['id']}/absentees", headers=admin).json() == []
    absent = client.get(f"/api/admin/events/{open_ev['id']}/absentees", headers=admin).json()
    assert [u["email"] for u in absent] == ["bob@test.io", "jane@test.io"]
    recent = {e["id"]: e for e in client.get("/api/admin/stats", headers=admin).json()["recent_events"]}
    assert recent[ev["id"]]["expected"] == 1 and recent[open_ev["id"]]["expected"] == 2

    # attendance filter by group; the user payload carries groups
    assert client.get("/api/admin/attendances", headers=admin, params={"group_id": gid}).json()["total"] == 1
    assert client.get("/api/auth/me", headers=user).json()["groups"][0]["name"] == "Team A"

    # membership change, then deleting the group re-opens the event to everyone
    client.patch(f"/api/admin/groups/{gid}", headers=admin, json={"member_ids": [users["bob@test.io"]]})
    assert ev["id"] in {e["id"] for e in client.get("/api/events", headers=bob).json()}
    client.delete(f"/api/admin/groups/{gid}", headers=admin)
    assert client.get(f"/api/events/{ev['id']}", headers=admin).json()["groups"] == []


def test_unknown_group_rejected(client, admin):
    now = datetime.now(UTC)
    r = client.post("/api/events", headers=admin, json={
        "title": "x", "starts_at": iso(now), "ends_at": iso(now + timedelta(hours=1)), "group_ids": [999]})
    assert r.status_code == 422
