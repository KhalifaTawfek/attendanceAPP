# Cases export review (2026-11-03)

`../Cases__1.csv` contains 16 open reports about this repository. Five repeat earlier
reports. The separate `../web-project-lab4/zammad/seed/tickets.json` describes a
different attendance project with professors, QR sessions, absence requests and
`uv.lock`; those features do not exist here.

| Case ID suffix | Report | Result in this repository |
|---|---|---|
| 398137 | Paper list import fails above 6 MB | An 11 MB upload through ngrok succeeded (HTTP 201) and its temporary import was deleted (204). Backend tests also cover transport of an 11 MB payload and decoding/storing a real large JPEG. The original failure was not reproducible on this deployment. |
| 398192, 402038 | Clear leaves search text; blur resets page | Search text follows the URL filter, Clear empties both, and unchanged blur does not reset pagination. |
| 398246, 402229 | CSV/Excel formula injection | Formula-leading text is escaped in both CSV and XLSX exports; tests check both formats. |
| 398300, 402175 | Rejected attendance counted present | Absentees, dashboard event counts and summary turnout exclude rejected submissions; tests cover all three. Status totals still show them. |
| 398346 | Insecure default secrets | Production rejects default or missing JWT/admin/database credentials. The deployed JWT secret was rotated. Local Compose requires secrets and binds ports to loopback. Grafana reader password comes from configuration. |
| 398400, 402325 | Tokens survive password reset and logout | A stored token version invalidates old tokens on password change, admin reset, account status or role change, and sign out. The browser awaits server revocation before clearing its session. Tests cover deactivation/reactivation and role changes. |
| 398454 | Admin list pagination and per-event query loop | User/event endpoints page at 200 records; the frontend loads all pages. Attendance summary computes expected counts from one membership query. |
| 398545, 402121 | Event-title search empties rate charts | Rate calculations include matching event titles as well as matching students; a regression test covers title search. |
| 399039 | Event form invalid/past dates and raw errors | New-event date inputs constrain past and reversed times; the form validates and shows readable messages. |
| 399131 | Bcrypt ignores password bytes after 72 | Registration, admin reset, password change and login reject passwords over 72 UTF-8 bytes, including multibyte characters in tests. |
| 402277 | Naive date filters skew PostgreSQL results | The API requires a timezone offset for date filters, then converts to UTC; a test checks rejection of naive input. |

The source CSV is a static export: its `Status` column still says `Open` for all 16
rows. Ticket status will be updated separately when the helpdesk is used again.

The Zammad tickets are not imported into this repo or this issue list because they
describe a different application and cannot be applied here without changing the
product's feature set.
