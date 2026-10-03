#!/usr/bin/env bash
set -euo pipefail

DRIVER="ODBC Driver 18 for SQL Server"

bash .github/scripts/install-unixodbc-ci.sh

if command -v odbcinst >/dev/null 2>&1 && odbcinst -q -d 2>/dev/null | grep -Fq "$DRIVER"; then
  echo "SQL Server ODBC CI: driver 18 já instalado."
  exit 0
fi

. /etc/os-release
if [[ "${ID:-}" != "ubuntu" || -z "${VERSION_ID:-}" ]]; then
  echo "::error::Runner não suportado para instalação governada do msodbcsql18."
  exit 6
fi

repo_deb="/tmp/packages-microsoft-prod.deb"
curl --fail --silent --show-error --location \
  --output "$repo_deb" \
  "https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/packages-microsoft-prod.deb"
sudo dpkg -i "$repo_deb"
sudo apt-get update -q
sudo env ACCEPT_EULA=Y DEBIAN_FRONTEND=noninteractive \
  apt-get install -y -q --no-install-recommends msodbcsql18

if ! odbcinst -q -d 2>/dev/null | grep -Fq "$DRIVER"; then
  echo "::error::ODBC Driver 18 for SQL Server não ficou registrado após instalação."
  exit 7
fi

echo "SQL Server ODBC CI: driver 18 instalado e verificado."
