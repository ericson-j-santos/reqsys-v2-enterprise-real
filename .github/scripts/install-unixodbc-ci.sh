#!/usr/bin/env bash
set -euo pipefail

PACKAGE="${ODBC_DEV_PACKAGE:-unixodbc-dev}"
ATTEMPTS="${ODBC_APT_ATTEMPTS:-2}"
TIMEOUT_SECONDS="${ODBC_APT_TIMEOUT_SECONDS:-45}"

if dpkg-query -W -f='${Status}' "${PACKAGE}" 2>/dev/null | grep -q 'ok installed'; then
  echo "ODBC CI: ${PACKAGE} já instalado; etapa de rede dispensada."
  exit 0
fi

for attempt in $(seq 1 "${ATTEMPTS}"); do
  echo "ODBC CI: tentativa ${attempt}/${ATTEMPTS} (timeout ${TIMEOUT_SECONDS}s por operação)."

  if timeout --preserve-status "${TIMEOUT_SECONDS}s" sudo apt-get update -q \
    && timeout --preserve-status "${TIMEOUT_SECONDS}s" sudo env DEBIAN_FRONTEND=noninteractive \
      apt-get install -y -q --no-install-recommends "${PACKAGE}"; then
    echo "ODBC CI: ${PACKAGE} instalado com sucesso."
    exit 0
  fi

  status=$?
  if [[ "${attempt}" -lt "${ATTEMPTS}" ]]; then
    delay=$((attempt * 3))
    echo "::warning::ODBC CI tentativa ${attempt}/${ATTEMPTS} falhou (status ${status}); retry em ${delay}s."
    sleep "${delay}"
  else
    echo "::error::ODBC CI falhou após ${ATTEMPTS} tentativas; preservando fail-closed."
    exit "${status}"
  fi
done
