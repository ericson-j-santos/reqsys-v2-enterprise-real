#!/bin/sh
set -eu
password="$(cat /run/secrets/db_app_password)"
# A senha gerada e hex: nao aceita SQL/metacaracteres vindos do arquivo.
case "$password" in *[!0-9a-f]*|"") echo "db_app_password invalido" >&2; exit 1;; esac
[ "${#password}" -eq 64 ] || exit 1
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<SQL
CREATE ROLE reqsys_app LOGIN PASSWORD '$password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE reqsys TO reqsys_app;
GRANT USAGE, CREATE ON SCHEMA public TO reqsys_app;
SQL
