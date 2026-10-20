-- For a natively installed PostgreSQL. Run as the postgres superuser:
--   psql -U postgres -f infra/postgres/setup-local.sql
CREATE ROLE attendance WITH LOGIN PASSWORD 'attendance';
CREATE DATABASE attendance OWNER attendance;
\connect attendance
\i infra/postgres/init/01-grafana-reader.sql
