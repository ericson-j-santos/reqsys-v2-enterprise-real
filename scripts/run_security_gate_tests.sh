#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d backend ]; then
  cd backend
fi

python -m pytest tests/test_security_production_gates_individual.py -v --tb=short
python -m pytest tests/test_security_cors_individual.py -v --tb=short
python -m pytest tests/test_security_auth_jwt_individual.py -v --tb=short
