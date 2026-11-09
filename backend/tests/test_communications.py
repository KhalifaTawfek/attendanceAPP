"""Announcements (newsletter) and polls: audience, authorization, anonymity, uniqueness."""
from datetime import UTC, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.models import Poll
from tests.conftest import auth_headers, png_bytes

PDF = b"%PDF-1.4\n% test document\n"


def future(hours=24):
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def make_user(client, admin, email, role="user"):
    r = client.post("/api/admin/users", headers=admin,
                    json={"email": email, "full_name": email.split("@")[0].title(), "password": "password123",
                          "role": role})
    assert r.status_code == 201, r.text
    return r.json()["id"], auth_headers(client, email, "password123")


def make_group(client, admin, name, member_ids):
    r = client.post("/api/admin/groups", headers=admin, json={"name": name, "member_ids": member_ids})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture()
def world(client, admin):
    """Two groups: A = {alice, bob}, B = {carol}; dave is in no group; a second admin."""
    ids, h = {}, {}
    for name in ("alice", "bob", "carol", "dave"):
        ids[name], h[name] = make_user(client, admin, f"{name}@test.io")
    ids["admin2"], h["admin2"] = make_user(client, admin, "admin2@test.io", role="admin")
    groups = {"A": make_group(client, admin, "Group A", [ids["alice"], ids["bob"]]),
              "B": make_group(client, admin, "Group B", [ids["carol"]])}
    return {"ids": ids, "h": h, "groups": groups}


# --- polls ----------------------------------------------------------------------
def make_poll(client, admin, **extra):
    body = {"title": "When do you want the exam?", "options": ["Monday", "Wednesday", "Friday"],
            "closes_at": future(), **extra}
    r = client.post("/api/polls", headers=admin, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def vote(client, headers, poll, index=0):
    return client.post(f"/api/polls/{poll['id']}/votes", headers=headers,
                       json={"option_id": poll["options"][index]["id"]})


def test_poll_defaults_and_aggregate_results(client, admin, world):
    poll = make_poll(client, admin, group_ids=[world["groups"]["A"]])
    assert poll["is_anonymous"] is True and poll["status"] == "open"
    assert poll["eligible_count"] == 2
    assert vote(client, world["h"]["alice"], poll, 0).status_code == 201
    assert vote(client, world["h"]["bob"], poll, 2).status_code == 201
    r = client.get(f"/api/polls/{poll['id']}", headers=admin).json()
    assert r["total_votes"] == 2
    assert [o["votes"] for o in r["options"]] == [1, 0, 1]
    assert [o["percentage"] for o in r["options"]] == [50.0, 0.0, 50.0]


def test_one_vote_per_user_and_votes_are_final(client, admin, world):
    poll = make_poll(client, admin, audience_all=True)
    assert vote(client, world["h"]["alice"], poll, 0).status_code == 201
    assert vote(client, world["h"]["alice"], poll, 1).status_code == 409
    assert client.get(f"/api/polls/{poll['id']}", headers=admin).json()["total_votes"] == 1


def test_anonymous_poll_never_reveals_choices(client, admin, world):
    poll = make_poll(client, admin, group_ids=[world["groups"]["A"]])
    vote(client, world["h"]["alice"], poll, 1)
    rows = client.get(f"/api/polls/{poll['id']}/voters", headers=admin).json()
    assert {r["user_id"]: r["voted"] for r in rows} == {world["ids"]["alice"]: True, world["ids"]["bob"]: False}
    assert all(r["option_id"] is None and r["voted_at"] is None for r in rows)


def test_named_poll_shows_each_choice_to_admins(client, admin, world):
    poll = make_poll(client, admin, group_ids=[world["groups"]["A"]], is_anonymous=False)
    vote(client, world["h"]["alice"], poll, 2)
    row = next(r for r in client.get(f"/api/polls/{poll['id']}/voters", headers=admin).json() if r["voted"])
    assert row["option_id"] == poll["options"][2]["id"] and row["voted_at"]


def test_results_hidden_from_users_until_they_vote(client, admin, world):
    poll = make_poll(client, admin, group_ids=[world["groups"]["A"]])
    vote(client, world["h"]["bob"], poll, 0)
    before = client.get(f"/api/polls/{poll['id']}", headers=world["h"]["alice"]).json()
    assert before["results_visible"] is False and before["total_votes"] is None
    assert all(o["votes"] is None for o in before["options"])
    after = vote(client, world["h"]["alice"], poll, 0).json()
    assert after["results_visible"] and after["total_votes"] == 2
    assert after["my_option_id"] == poll["options"][0]["id"] and after["has_voted"]


def test_only_targeted_group_members_see_and_vote(client, admin, world):
    poll = make_poll(client, admin, group_ids=[world["groups"]["A"]])
    for outsider in ("carol", "dave"):
        assert client.get(f"/api/polls/{poll['id']}", headers=world["h"][outsider]).status_code == 404
        assert vote(client, world["h"][outsider], poll).status_code == 404
        assert client.get("/api/polls", headers=world["h"][outsider]).json() == []
    multi = make_poll(client, admin, group_ids=[world["groups"]["A"], world["groups"]["B"]])
    assert vote(client, world["h"]["carol"], multi).status_code == 201
    assert multi["eligible_count"] == 3


def test_leaving_the_group_removes_access(client, admin, world):
    poll = make_poll(client, admin, group_ids=[world["groups"]["A"]])
    client.patch(f"/api/admin/groups/{world['groups']['A']}", headers=admin, json={"member_ids": [world["ids"]["bob"]]})
    assert vote(client, world["h"]["alice"], poll).status_code == 404


def test_only_the_author_manages_a_poll(client, admin, world):
    poll = make_poll(client, admin, audience_all=True)
    other = world["h"]["admin2"]
    assert client.get(f"/api/polls/{poll['id']}", headers=other).json()["can_manage"] is False
    assert client.post(f"/api/polls/{poll['id']}/close", headers=other).status_code == 403
    assert client.delete(f"/api/polls/{poll['id']}", headers=other).status_code == 403
    assert client.get(f"/api/polls/{poll['id']}", headers=admin).json()["can_manage"] is True


def test_users_cannot_create_close_or_see_voters(client, admin, world):
    alice = world["h"]["alice"]
    r = client.post("/api/polls", headers=alice, json={"title": "x", "options": ["a", "b"],
                                                       "closes_at": future(), "audience_all": True})
    assert r.status_code == 403
    poll = make_poll(client, admin, audience_all=True)
    assert client.post(f"/api/polls/{poll['id']}/close", headers=alice).status_code == 403
    assert client.get(f"/api/polls/{poll['id']}/voters", headers=alice).status_code == 403
    assert vote(client, admin, poll).status_code == 403  # admins don't vote


def test_closing_early_stops_votes_and_reveals_results(client, admin, world):
    poll = make_poll(client, admin, audience_all=True)
    closed = client.post(f"/api/polls/{poll['id']}/close", headers=admin)
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    assert client.post(f"/api/polls/{poll['id']}/close", headers=admin).status_code == 409
    assert vote(client, world["h"]["alice"], poll).status_code == 409
    seen = client.get(f"/api/polls/{poll['id']}", headers=world["h"]["alice"]).json()
    assert seen["results_visible"] is True
    assert client.get("/api/polls?status=open", headers=world["h"]["alice"]).json() == []
    assert len(client.get("/api/polls?status=closed", headers=world["h"]["alice"]).json()) == 1


def test_deadline_passed_blocks_voting(client, admin, world):
    poll = make_poll(client, admin, audience_all=True)
    with SessionLocal() as db:
        db.get(Poll, poll["id"]).closes_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert vote(client, world["h"]["alice"], poll).status_code == 409
    assert client.get(f"/api/polls/{poll['id']}", headers=admin).json()["status"] == "closed"


def test_option_must_belong_to_the_poll(client, admin, world):
    first, second = make_poll(client, admin, audience_all=True), make_poll(client, admin, audience_all=True)
    r = client.post(f"/api/polls/{first['id']}/votes", headers=world["h"]["alice"],
                    json={"option_id": second["options"][0]["id"]})
    assert r.status_code == 422


def test_poll_validation(client, admin, world):
    def create(**overrides):
        body = {"title": "Q", "options": ["A", "B"], "closes_at": future(), "audience_all": True, **overrides}
        return client.post("/api/polls", headers=admin, json=body).status_code

    assert create(options=["only one"]) == 422
    assert create(options=[str(i) for i in range(9)]) == 422
    assert create(options=["Same", "same"]) == 422
    assert create(options=["A", "  "]) == 422
    assert create(closes_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat()) == 422
    assert create(closes_at=datetime.now().replace(microsecond=0).isoformat()) == 422  # no timezone
    assert create(audience_all=False) == 422  # no audience
    assert create(audience_all=False, group_ids=[999]) == 422
    assert create(title="   ") == 422
    assert create(options=[str(i) for i in range(8)]) == 201


def test_deleting_a_poll_removes_its_votes(client, admin, world):
    poll = make_poll(client, admin, audience_all=True)
    vote(client, world["h"]["alice"], poll)
    assert client.delete(f"/api/polls/{poll['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/polls/{poll['id']}", headers=admin).status_code == 404


# --- announcements ------------------------------------------------------------------
def send(client, admin, **body):
    return client.post("/api/announcements", headers=admin,
                       json={"title": "Exam moved", "body": "The exam is now on **Friday**.", **body})


def test_announcement_reaches_only_its_audience(client, admin, world):
    r = send(client, admin, group_ids=[world["groups"]["A"]])
    assert r.status_code == 201, r.text
    sent = r.json()
    assert sent["recipient_count"] == 2 and sent["read_count"] == 0 and sent["can_manage"]
    inbox = client.get("/api/announcements", headers=world["h"]["alice"]).json()
    assert [a["id"] for a in inbox] == [sent["id"]] and inbox[0]["read_at"] is None
    assert inbox[0]["recipient_count"] is None  # admin-only fields stay hidden
    assert client.get("/api/announcements", headers=world["h"]["carol"]).json() == []
    assert client.get(f"/api/announcements/{sent['id']}", headers=world["h"]["carol"]).status_code == 404


def test_announcement_to_several_groups_and_everyone(client, admin, world):
    both = send(client, admin, group_ids=[world["groups"]["A"], world["groups"]["B"]]).json()
    assert both["recipient_count"] == 3
    everyone = send(client, admin, audience_all=True).json()
    assert everyone["recipient_count"] == 4  # dave too; admins aren't recipients
    assert len(client.get("/api/announcements", headers=world["h"]["dave"]).json()) == 1


def test_mark_read_and_inbox_counts(client, admin, world):
    alice = world["h"]["alice"]
    sent = send(client, admin, audience_all=True).json()
    make_poll(client, admin, audience_all=True)
    assert client.get("/api/inbox", headers=alice).json() == {"unread_announcements": 1, "polls_to_vote": 1}
    first = client.post(f"/api/announcements/{sent['id']}/read", headers=alice).json()
    again = client.post(f"/api/announcements/{sent['id']}/read", headers=alice).json()
    assert first["read_at"] and again["read_at"] == first["read_at"]
    assert client.get("/api/announcements?unread=true", headers=alice).json() == []
    assert client.get("/api/inbox", headers=alice).json()["unread_announcements"] == 0
    assert client.get(f"/api/announcements/{sent['id']}", headers=admin).json()["read_count"] == 1
    readers = client.get(f"/api/announcements/{sent['id']}/readers", headers=admin).json()
    assert sum(1 for r in readers if r["read_at"]) == 1 and len(readers) == 4


def test_announcement_authorization(client, admin, world):
    assert send(client, world["h"]["alice"], audience_all=True).status_code == 403
    assert send(client, admin).status_code == 422  # no audience
    sent = send(client, admin, audience_all=True).json()
    assert client.delete(f"/api/announcements/{sent['id']}", headers=world["h"]["admin2"]).status_code == 403
    assert client.post(f"/api/announcements/{sent['id']}/read", headers=admin).status_code == 403
    assert client.get(f"/api/announcements/{sent['id']}/readers", headers=world["h"]["alice"]).status_code == 403


def test_announcement_attachment(client, admin, world):
    sent = send(client, admin, group_ids=[world["groups"]["A"]]).json()
    url = f"/api/announcements/{sent['id']}/attachment"
    bad = client.post(url, headers=admin, files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 422
    assert client.post(url, headers=world["h"]["admin2"], files={"file": ("x.pdf", PDF)}).status_code == 403
    ok = client.post(url, headers=admin, files={"file": ("syllabus.pdf", PDF, "application/pdf")})
    assert ok.status_code == 200 and ok.json()["has_attachment"] and ok.json()["attachment_name"] == "syllabus.pdf"
    got = client.get(url, headers=world["h"]["alice"])
    assert got.status_code == 200 and got.content == PDF and got.headers["x-content-type-options"] == "nosniff"
    assert client.get(url, headers=world["h"]["carol"]).status_code == 404
    image = client.post(url, headers=admin, files={"file": ("photo.png", png_bytes(), "image/png")}).json()
    assert image["attachment_type"] == "image/jpeg" and image["attachment_name"] == "photo.jpg"


def test_delete_announcement(client, admin, world):
    sent = send(client, admin, audience_all=True).json()
    client.post(f"/api/announcements/{sent['id']}/read", headers=world["h"]["alice"])
    assert client.delete(f"/api/announcements/{sent['id']}", headers=admin).status_code == 204
    assert client.get("/api/announcements", headers=world["h"]["alice"]).json() == []
