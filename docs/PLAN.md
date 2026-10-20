# Attendance App — Requirements & Plan

## 1. Requirements (as stated)

| # | Requirement | Covered by |
|---|-------------|-----------|
| R1 | FastAPI backend | `backend/` (FastAPI + SQLAlchemy 2 + Alembic) |
| R2 | React frontend | `frontend/` (Vite + React + TypeScript) |
| R3 | PostgreSQL storage | `psycopg` 3 driver, Alembic migrations |
| R4 | Grafana observability | `/metrics` (Prometheus) → Prometheus → Grafana; Grafana also queries Postgres directly for business dashboards |
| R5 | Admin dashboard: view, filter, export attendances | `/admin/attendances` (filters + pagination), CSV & XLSX export |
| R6 | Users are enrolled and have their own accounts | Admin enrolls users (email + temp password); users log in and can change password |
| R7 | Users upload a picture of their presence | Multipart upload, validated & re-encoded with Pillow (EXIF stripped), stored on disk, served only to owner/admin |
| R8 | Users complete a short form to validate presence | Form: activity summary (required), location note (optional), honesty declaration (required checkbox) |
| R9 | Admin creates events (point in time of the activity) | Event: title, description, location, `starts_at`, `ends_at`, check-in window |
| R10 | Use a virtual environment | `backend/.venv` |
| R11 | Recurring events | Daily / weekly (chosen weekdays) / monthly series with interval, ending after N occurrences or on a date; edit/delete one, this-and-following, or all |
| R12 | User groups for events | Admin-managed groups; an event limited to groups is only visible to, and expected from, their members |
| R13 | No GPS capture | Removed (migration 0002 drops the columns); free-text location note kept |
| R14 | CI/CD pipeline | GitHub Actions: Postgres-backed tests + migration checks, frontend lint/build, Docker images pushed to GHCR |

## 2. Validation — ambiguities & the assumptions made

| Question | Decision |
|---|---|
| Who creates accounts? | **Admin enrolls** users. Self-registration is off by default (`ALLOW_SELF_REGISTRATION=false`) but supported. |
| Who is expected at an event? | Events with no groups: all active users. Events with groups: active members of any of those groups. "Absent" = expected users with no submission. |
| How are recurring events stored? | A rule row (`event_series`) plus one concrete `events` row per occurrence (max 200), so each occurrence has its own attendance and can be edited/cancelled individually. Occurrences are computed in the creator's timezone so local time is stable across DST. |
| Editing a series | Scope `this` / `future` / `all`. Text, group and late-threshold changes are copied; time changes are applied as the same shift to every targeted occurrence. |
| When can a user check in? | Inside the event's check-in window: `check_in_opens_at` (default `starts_at - 15 min`) to `check_in_closes_at` (default `ends_at`). After `starts_at + late_after_minutes` (default 10) the record is flagged **late**. |
| How many submissions per event? | **One per user per event** (DB unique constraint). |
| Does the photo prove presence automatically? | No face recognition (out of scope). Admin **reviews**: status `pending → approved / rejected` with an optional comment. |
| Photo limits | JPEG/PNG/WebP, ≤ 5 MB, re-encoded to JPEG ≤ 1600 px. |
| Export formats | CSV and Excel (XLSX), honouring current filters. |
| Auth | JWT bearer tokens (HS256), bcrypt password hashing, roles `admin` / `user`. First admin seeded from env. |
| Timezones | All timestamps stored in UTC (`timestamptz`); the UI shows local time. |

## 3. Data model

- **users**: id, email (unique), full_name, password_hash, role, is_active, created_at
- **events**: id, title, description, location, starts_at, ends_at, check_in_opens_at, check_in_closes_at, late_after_minutes, created_by, created_at
- **attendances**: id, event_id, user_id, photo_path, activity_summary, location_note, declaration, is_late, status, review_comment, reviewed_by, reviewed_at, submitted_at — unique(event_id, user_id)
- **groups**: id, name (unique), description, created_at; **group_members** (group_id, user_id)
- **event_groups** (event_id, group_id)
- **event_series**: id, frequency, interval, weekdays, until, count, timezone; **events.series_id** → event_series

## 4. API (prefix `/api`)

- `POST /auth/login`, `POST /auth/register` (if enabled), `GET /auth/me`, `POST /auth/change-password`
- `GET /events` (user: open/upcoming for their groups; admin: all), `POST /events` (optional `recurrence`, `group_ids`; returns all occurrences), `PATCH/DELETE /events/{id}?scope=this|future|all` (admin)
- Admin: `GET/POST /admin/groups`, `PATCH/DELETE /admin/groups/{id}`
- `POST /attendances` (multipart), `GET /attendances/me`, `GET /attendances/{id}/photo`
- Admin: `GET/POST/PATCH /admin/users`, `GET /admin/attendances`, `PATCH /admin/attendances/{id}`, `GET /admin/attendances/export?format=csv|xlsx`, `GET /admin/stats`, `GET /admin/events/{id}/absentees`
- `GET /health`, `GET /metrics`

## 5. Observability

- HTTP metrics (rate, latency histogram, status codes) via `prometheus-fastapi-instrumentator`.
- Business metrics: `attendance_submissions_total{late}`, `attendance_reviews_total{status}`, `login_attempts_total{result}`.
- Grafana provisioned with Prometheus + Postgres datasources and two dashboards: **API Health** and **Attendance Overview**.

## 6. Running

- Infra via `docker compose up -d` (Postgres, Prometheus, Grafana; optionally backend/frontend), **or** natively installed Postgres + Grafana.
- Backend: `backend/.venv` → `alembic upgrade head` → `uvicorn app.main:app`.
- Frontend: `npm install && npm run dev` (proxies `/api` to the backend).

## 7. Out of scope (possible next steps)

Face matching, email notifications, SSO, log aggregation (Loki), deployment target for the built images.
