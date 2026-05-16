# AGENTS.md

Guia rápido para agentes automatizados que trabalham neste repositório. Os comandos abaixo foram extraídos de `README.md`, `package.json` (raiz e por frontend), `.github/workflows/ci.yml` e `scripts/`.

## Layout

- `backend/` — FastAPI + SQLAlchemy + Pydantic (Python 3.12). Testes em `backend/tests/`.
- `frontend/` — Vue 3 + Vuetify (Vite). Frontend principal de produção.
- `frontend-vuetify/` — variante Vuetify alternativa (Vitest).
- `frontend-angular/` — variante Angular 17 (Jest).
- `e2e/` — specs Playwright multi-frontend (Vuetify e Angular).
- `scripts/` — automação local (bash + PowerShell).
- `.github/workflows/ci.yml` — pipeline de CI.

## Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload      # script equivalente: scripts/executar-local.sh
```

Testes:

```bash
cd backend
python -m pytest                   # ou: PYTHONPATH=. pytest -q
```

Variáveis usadas no CI (`backend-test`): `DATABASE_URL=sqlite:///./reqsys_test.db`, `JWT_SECRET_KEY`, `REDMINE_URL`, `REDMINE_API_KEY`, `ENABLE_GITHUB_REDMINE_IMPORT=false`, `SSRS_BASE_URL=""`.

## Frontends

| Pasta              | Dev                 | Build              | Testes                   |
| ------------------ | ------------------- | ------------------ | ------------------------ |
| `frontend/`        | `npm run dev`       | `npm run build`    | `npm run test:e2e:stable` (Playwright, runner `scripts/run-e2e-safe.js`) |
| `frontend-vuetify/`| `npm run dev`       | `npm run build`    | `npm run test` / `npm run test:coverage` (Vitest) |
| `frontend-angular/`| `npm start`         | `npm run build`    | `npm test` / `npm run test:coverage` (Jest) |

CI (`frontend-build`) usa Node 20 e roda `npm ci && npm run build` em `frontend/` com `VITE_API_URL=/api`.

## E2E na raiz (Playwright multi-frontend)

Definidos em `package.json` da raiz e em `playwright.config.ts`:

```bash
npm run test:e2e          # playwright test
npm run test:e2e:ui       # --ui
npm run test:e2e:debug    # --debug
npm run test:e2e:report   # show-report
```

## Stack completo via Docker

```bash
docker compose up --build                                   # padrão (dev)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Wrapper: `scripts/publicar_ambiente.sh {dev|hml|prod}`.

## Validação consolidada

`scripts/validar_qualidade.sh` executa, nesta ordem: pytest no backend, `npm run build` em `frontend-vuetify` e `frontend-angular`, e `npm run test:e2e` na raiz.

## Scripts PowerShell (Windows)

- `scripts/executar-snapshot-qualidade-ia.ps1` — snapshot manual de qualidade de IA.
- `scripts/agendar-snapshot-qualidade-ia.ps1 -Hora 8 -Minuto 0` — agenda execução diária.
- `scripts/configurar-ssrs.ps1` — configura integração SSRS.
- `scripts/reiniciar-docker-seguro.ps1`, `scripts/reiniciar-stack-limpo.ps1`, `scripts/subir-stack-sem-colisao.ps1` — utilidades de stack.

Logs de execução dos scripts ficam em `backend/scripts_audit/logs/`.

## Convenções para agentes

- Não comitar `backend/reqsys.db` nem artefatos gerados (`.venv/`, `node_modules/`, `dist/`).
- Antes de editar workflows automatizados (`.github/workflows/*`, `scripts/*`), verificar uso atual no `README.md` e neste arquivo.
- Para tarefas exclusivamente de revisão (sem mudanças), não criar nem modificar arquivos no repositório.

<!-- TODO: documentar comandos de lint/format quando forem adicionados ao repo (atualmente não há scripts de lint definidos em package.json nem hooks/configs detectados). -->
