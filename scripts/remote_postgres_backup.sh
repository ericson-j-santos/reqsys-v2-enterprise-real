#!/bin/sh
set -eu

target="${1:?target .tar.gz path is required}"

case "$target" in
  /tmp/*.tar.gz) ;;
  *)
    echo "target must be an explicit /tmp/*.tar.gz path" >&2
    exit 2
    ;;
esac

workdir="/tmp/flyio-retirement-postgres.$$"
trap 'rm -rf "$workdir"' EXIT
mkdir -p "$workdir"
rm -f "$target"

su postgres -c \
  "psql -p 5433 -Atqc \"SELECT datname FROM pg_database WHERE datallowconn AND datname NOT IN ('postgres', 'template0', 'template1') ORDER BY datname\"" \
  > "$workdir/databases.txt"

while IFS= read -r database; do
  case "$database" in
    ''|*[!A-Za-z0-9_-]*)
      echo "unsafe database name in inventory" >&2
      exit 3
      ;;
  esac
  dump="$workdir/database-$database.dump"
  su postgres -c "pg_dump -p 5433 -Fc --dbname=\"$database\"" > "$dump"
  pg_restore --list "$dump" > /dev/null
done < "$workdir/databases.txt"

su postgres -c "pg_dumpall -p 5433 --globals-only --no-role-passwords" \
  | gzip -9 > "$workdir/globals.sql.gz"
gzip -t "$workdir/globals.sql.gz"
(cd "$workdir" && sha256sum databases.txt globals.sql.gz database-*.dump > checksums.sha256)
tar -C "$workdir" -czf "$target" .
tar -tzf "$target" > /dev/null
sha256sum "$target"
stat -c '%s bytes' "$target"
