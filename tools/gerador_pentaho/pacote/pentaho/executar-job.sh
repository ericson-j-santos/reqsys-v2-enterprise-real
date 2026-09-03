#!/usr/bin/env sh
set -eu
: "${KETTLE_HOME:?Defina KETTLE_HOME apontando para data-integration}"
BASE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$KETTLE_HOME/kitchen.sh" -file="$BASE_DIR/jobs/jb_treino_criar_dossies.kjb" -level=Basic

