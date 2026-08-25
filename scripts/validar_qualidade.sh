#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Guardrail de frontends legados"
python scripts/validate_legacy_frontend_references.py

echo "[2/4] Testes backend"
(
  cd backend
  PYTHONPATH=. pytest -q
)

echo "[3/4] Build UI canônica"
(
  cd frontend
  npm run build
)

echo "[4/4] E2E governado da UI canônica"
(
  cd frontend
  npm run test:e2e -- \
    tests/e2e/login-accessibility.spec.js \
    tests/e2e/responsividade.spec.js \
    tests/e2e/estatistica-detalhe.spec.js \
    --reporter=line
)
