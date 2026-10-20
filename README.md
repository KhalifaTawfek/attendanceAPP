# Attendance App

Attendance tracking with photo + form check-ins, an admin dashboard, and Grafana observability.

- **Backend**: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (`backend/`)
- **Frontend**: React + TypeScript + Vite (`frontend/`)
- **Observability**: Prometheus metrics at `/metrics`, Grafana dashboards (`infra/grafana/`)

Requirements, assumptions and design: [docs/PLAN.md](docs/PLAN.md).

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

## Quick start (Docker)

```bash
docker compose up -d                    # postgres, prometheus, grafana
docker compose --profile app up -d      # + backend (8000) and frontend (8080)
```

- App: http://localhost:8080 (admin: `admin@example.com` / `admin12345`)
- Grafana: http://localhost:3000 (`admin` / `admin`), folder **Attendance**
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

The tests run against a temporary SQLite database. They cover auth and roles, the check-in window and late flag, duplicate prevention, image validation, photo privacy, review, filters, absentees, CSV/XLSX export, recurrence expansion (including DST), series-scoped edits, and group-restricted events.

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
