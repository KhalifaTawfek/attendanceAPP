# Attendance App

Attendance tracking with photo + form check-ins, an admin dashboard, and Grafana observability.

- **Backend**: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (`backend/`)
- **Frontend**: React + TypeScript + Vite (`frontend/`)
- **Observability**: Prometheus metrics at `/metrics`, Grafana dashboards (`infra/grafana/`)

Requirements, assumptions and design: [docs/PLAN.md](docs/PLAN.md).

Deployment using GitHub Pages for the frontend and ngrok on a Windows PC for the backend: [docs/DEPLOY-GITHUB-NGROK.md](docs/DEPLOY-GITHUB-NGROK.md).

## Features

**Users** sign in with an account the admin enrolled, see the events for their groups whose check-in is open, and check in by uploading a photo and filling out a short form: activity summary, an optional location note, and a presence declaration. They can see their history and its review status, and change their password.

**Admins** can:
- see a dashboard of KPIs and per-event turnout
- create, edit and delete events, each with a check-in window and a "late after" threshold
- make events recurring (daily, weekly on chosen weekdays, or monthly; N times or until a date) and edit or delete one occurrence, this and following, or the whole series
- manage user groups and limit events to them, so only members see the event and only members count as expected
- enroll, disable and promote users, and reset their passwords
- browse attendances with filters (event, user, group, status, late, date range, free text), sorting and pagination
- review each submission (photo and form) and approve or reject it with a comment
- export the current filter as **CSV** or **Excel**
- see who has not checked in for an event
- send **announcements** (newsletter) and run **polls** — see below

## Quick start (Docker)

Copy `.env.example` to `.env` and set every blank password/secret. Set `DATABASE_URL` to
`postgresql+psycopg://attendance:<POSTGRES_PASSWORD>@postgres:5432/attendance`
(URL-encode special characters in the password). The local services bind to `127.0.0.1`.

```bash
docker compose up -d                    # postgres, prometheus, grafana
docker compose --profile app up -d      # + backend (8000) and frontend (8080)
```

- App: http://localhost:8080 (admin email and password from `.env`)
- Grafana: http://localhost:3000 (`admin` / `GRAFANA_ADMIN_PASSWORD` from `.env`), folder **Attendance**
- Prometheus: http://localhost:9090

## Local development (Windows, venv)

1. **Database**: either `docker compose up -d postgres`, or with a native PostgreSQL:
   ```powershell
   & "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -f infra/postgres/setup-local.sql
   ```
2. **Backend**:
   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1          # venv already created; else: python -m venv .venv
   pip install -r requirements.txt
   copy .env.example .env                # then edit JWT_SECRET / admin credentials
   alembic upgrade head
   uvicorn app.main:app --reload         # http://localhost:8000/docs
   ```
   On first start the admin account from `.env` is created.
   Optional demo users (all with password `test`): `python -m app.seed`.
3. **Frontend**:
   ```powershell
   cd frontend
   npm install
   npm run dev                           # http://localhost:5173, proxies /api -> :8000
   ```
4. **Observability**: `docker compose up -d prometheus grafana`. Prometheus also scrapes a backend running on the host (`host.docker.internal:8000`).
   For a native Grafana install, copy `infra/grafana/provisioning/*` into Grafana's `conf/provisioning`, set the env vars `PROMETHEUS_URL=http://localhost:9090` and `PG_HOST=localhost:5432`, and change the dashboards provider `path` to the absolute path of `infra/grafana/dashboards`.

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest -q
```

The tests run against a temporary SQLite database. They cover auth and roles, the check-in window and late flag, duplicate prevention, image validation, photo privacy, review, filters, absentees, CSV/XLSX export, recurrence expansion (including DST), series-scoped edits, group-restricted events, and announcements/polls (audience, authorship, anonymity, one vote per student, deadlines, attachments).

## Announcements (newsletter) and polls

In this app the professor is an **admin** and a student is a **user**; "sections" are **groups**.

**Announcements** (`/admin/announcements`, students: `/announcements`)
- An admin writes a title and a Markdown body (bold, italic, code, headings, lists, `https` links; a safe subset rendered without HTML), optionally attaches one PDF or image (max `MAX_UPLOAD_MB`; images are re-encoded and stripped of metadata like check-in photos), and sends it to **everyone** or to one or more **groups**.
- Students see what was sent to them, newest first, with unread ones highlighted and counted in the navigation. Opening one marks it read.
- Admins see "read by X of Y" and who hasn't opened it yet. Only the author can delete it.

**Polls** (`/admin/polls`, students: `/polls`)
- An admin asks a question with 2–8 options, a deadline, and an audience (everyone or groups). Polls are **anonymous by default**.
- A student in the audience votes for exactly one option. **Votes are final**: they can't be changed or withdrawn (simplest rule to reason about, and it stops answers from being steered by the running totals). The database enforces one vote per student per poll (`uq_poll_vote_user`).
- Students don't see results until they've voted or the poll has closed. Then they see totals and percentages, and which option was theirs.
- Admins see live results (refreshed every 4 s) and the list of who has and hasn't voted. For anonymous polls that list has no choice and no vote time — a vote time next to live totals would give the choice away. For named polls (`is_anonymous: false`, students are told before voting) admins also see each choice.
- Only the poll's author can close it early or delete it; other admins can view it. Admins can't vote.
- Access follows group membership live: someone added to a targeted group later can vote, someone removed loses access. Anything a student isn't allowed to see answers 404.
- Limitation: with very few voters, totals alone can reveal a vote (e.g. 1 vote total). Anonymity protects the stored link between person and choice, not small-number inference.

**API** (all under `/api`, JWT bearer auth, see `/docs`)

| Method & path | Who | |
|---|---|---|
| `POST /announcements` | admin | `{title, body, audience_all, group_ids}` |
| `GET /announcements[?unread=true&group_id=]` | both | admins: all; users: theirs |
| `GET /announcements/{id}` · `POST /announcements/{id}/read` | both · user | |
| `GET /announcements/{id}/readers` | admin | |
| `POST\|GET /announcements/{id}/attachment` · `DELETE /announcements/{id}` | author · audience · author | |
| `POST /polls` | admin | `{title, description, options[2..8], closes_at (with offset), is_anonymous=true, audience_all, group_ids}` |
| `GET /polls[?status=open\|closed&group_id=]` · `GET /polls/{id}` | both | counts hidden from users until they vote / it closes |
| `POST /polls/{id}/votes` | user | `{option_id}`; 409 if already voted or closed |
| `POST /polls/{id}/close` · `DELETE /polls/{id}` | author | |
| `GET /polls/{id}/voters` | admin | |
| `GET /inbox` | user | `{unread_announcements, polls_to_vote}` for the nav badges |

Database: migration `0005` adds `announcements`, `announcement_groups`, `announcement_reads`, `polls`, `poll_groups`, `poll_options`, `poll_votes`. No new environment variables.

## Importing paper attendance lists

Under **Import list**, an admin uploads one or more photos of a signed paper list:

1. **Read:** the sheet is located and straightened in the photo, then Tesseract reads it.
2. **Correct:** each line is cleaned up (numbering, group codes, "Erasmus", dates and grades are dropped) and fuzzy-matched against active students. Each student is matched to at most one line.
3. **Deduplicate:** names repeated across lines or photos, and students already recorded for the event, are flagged rather than saved twice.
4. **Review:** confident matches and plausible ones are pre-selected; unreadable lines are left for the admin to assign or skip. The date is read from the sheet, or the photo's camera date is offered. If it's unclear, the admin picks the day and the event, and can create one on the spot. One sheet can be saved to several events, e.g. two sessions.
5. **Save:** creates approved attendances marked **Paper list**, with the photo kept as evidence.

Tesseract has to be installed on the server. On Windows: `winget install UB-Mannheim.TesseractOCR`; the Docker image already includes it. To try the pipeline on an image without saving anything: `python -m app.ocr.evaluate list.jpg`.

Tesseract is weak on handwriting, so most of the accuracy comes from matching against the roster. On a test photo of a handwritten list it pre-selected 16 of 19 students correctly, with no false matches. The rest were left for the admin.

The **Attendances** page has filters for source (self check-in or paper list), group and event date range. It also shows charts for the current filters: attendance per event against the expected number, review status, source, by group, and most present. Click a chart to filter by it, or switch any chart to a table.

## CI/CD

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on pushes to `main`, on `v*` tags and on pull requests:

1. **Backend**: on a Postgres 17 service, it applies the migrations, runs `alembic check` to catch model/migration drift, rolls back and re-applies, then runs pytest.
2. **Frontend**: `npm ci`, lint, then a type-checked build.
3. **Images**: once both pass, it builds the backend and frontend Docker images. On `main` and on tags it pushes them to GHCR as `ghcr.io/<owner>/<repo>-backend` and `-frontend`, tagged `latest`, with the short SHA, and with the version for tags. Pull requests build the images without pushing.

To run the tests against Postgres locally, set `TEST_DATABASE_URL`. It must point to a disposable database, because the tests drop all tables.

## Metrics

| Metric | Labels |
|---|---|
| `http_requests_total`, `http_request_duration_seconds` | handler, method, status |
| `attendance_submissions_total` | late |
| `attendance_reviews_total` | status |
| `login_attempts_total` | result |

Grafana dashboards:
- **Attendance API Health** (Prometheus): uptime, throughput, error ratio, latency percentiles, business counters.
- **Attendance Overview** (PostgreSQL, read-only `grafana_reader` role): submissions over time, status split, turnout per event, top attendees.

## Production notes

- Set a strong `JWT_SECRET` and change the default admin, Postgres and Grafana passwords.
- Photos are stored in `UPLOAD_DIR` (a Docker volume) and are only served to their owner or to admins.
- Put the app behind HTTPS. Browsers only allow camera capture and geolocation on secure origins (localhost is fine).
