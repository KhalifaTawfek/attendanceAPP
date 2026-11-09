#!/bin/sh
set -eu

: "${GRAFANA_DB_PASSWORD:?Set GRAFANA_DB_PASSWORD before initializing PostgreSQL}"
psql -v ON_ERROR_STOP=1 -v reader_password="$GRAFANA_DB_PASSWORD" \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
CREATE ROLE grafana_reader WITH LOGIN PASSWORD :'reader_password';
GRANT CONNECT ON DATABASE attendance TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE attendance IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;
SQL
