-- For a natively installed PostgreSQL. Run as the postgres superuser:
--   psql -U postgres -f infra/postgres/setup-local.sql
\prompt 'Password for attendance role: ' attendance_password
CREATE ROLE attendance WITH LOGIN PASSWORD :'attendance_password';
CREATE DATABASE attendance OWNER attendance;
\connect attendance
\prompt 'Password for Grafana reader role: ' grafana_db_password
CREATE ROLE grafana_reader WITH LOGIN PASSWORD :'grafana_db_password';
GRANT CONNECT ON DATABASE attendance TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE attendance IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;
