#!/bin/sh
set -eu
# Solo se ejecuta al inicializar un volumen nuevo. Ninguna credencial va a stdout.
export RISK_APP_PASSWORD="$(cat "$APP_DB_PASSWORD_FILE")"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
\getenv app_password RISK_APP_PASSWORD
\getenv database_name POSTGRES_DB
CREATE ROLE riesgo_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE :"database_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"database_name" TO riesgo_app;
ALTER ROLE riesgo_app SET timezone TO 'UTC';
ALTER ROLE riesgo_owner SET timezone TO 'UTC';
SQL
unset RISK_APP_PASSWORD
