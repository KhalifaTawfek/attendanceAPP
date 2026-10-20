-- Read-only role used by Grafana's PostgreSQL datasource.
CREATE ROLE grafana_reader WITH LOGIN PASSWORD 'grafana_reader';
GRANT CONNECT ON DATABASE attendance TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
-- Tables are created later by Alembic (as the attendance user), so grant on future tables too.
ALTER DEFAULT PRIVILEGES FOR ROLE attendance IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;
