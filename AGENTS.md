# AGENTS.md

Operational notes for agents working in this repository. Keep concise and
grounded in actual repo usage. Refer to `README.md` for full context.

## Repo layout

- `backend/` — FastAPI service (Python). Tests in `backend/tests/`.
- `backend-dotnet/` — ASP.NET Core 8 service (`ReqSys.DotNet.sln`).
- `frontend/` — Vue 3 + Vuetify app (current primary frontend).
- `frontend-vuetify/` — Vue 3 + Vuetify app used by root Playwright E2E
  (served on `:5174`).
- `frontend-angular/` — Angular 17 app used by root Playwright E2E
  (served on `:4200`).
- `e2e/` — Cross-frontend Playwright specs (`*-vuetify.spec.ts`,
  `*-angular.spec.ts`) driven by `playwright.config.ts` at the repo root.
- `infra/nginx/` — Nginx configs per environment.
- `scripts/` — PowerShell + shell automation (local run, snapshots,
  scheduling, endpoint checks).

## Common commands

### Backend (FastAPI, Python)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload      # dev server on :8000
python -m pytest                   # tests
```

### Backend .NET

```bash
cd backend-dotnet
dotnet restore ReqSys.DotNet.sln
dotnet test ReqSys.DotNet.sln
dotnet run --project src/ReqSys.Api/ReqSys.Api.csproj
```

### Frontend (Vue + Vuetify, primary)

```bash
cd frontend
npm install
npm run dev                        # Vite, host 0.0.0.0
npm run build
npm run test:e2e                   # Playwright (frontend-local)
npm run test:e2e:stable            # node scripts/run-e2e-safe.js (pre-flight + retries:1)
```

### Frontend Vuetify (root E2E target)

```bash
cd frontend-vuetify
npm install
npm run dev                        # Vite, host 0.0.0.0
npm run test                       # vitest run
npm run test:coverage
```

### Frontend Angular

```bash
cd frontend-angular
npm install
npm start                          # ng serve --host 0.0.0.0 --port 4200
npm run build
npm test                           # jest
npm run test:coverage
```

### Root Playwright (cross-frontend)

```bash
npm install
npx playwright install --with-deps  # first time only
npm run test:e2e                    # runs both vuetify (:5174) and angular (:4200) projects
npm run test:e2e:ui
npm run test:e2e:debug
npm run test:e2e:report
```

The root `playwright.config.ts` auto-starts `frontend-vuetify` (Vite) and
`frontend-angular` (`ng serve` with `proxy.conf.json`) via `webServer`.

### Docker Compose

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml  up --build -d   # dev   :8083 / api :8211
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build -d   # test  :8084 / api :8212
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d   # prod  :8081
```

### Local run without Docker

```bash
bash scripts/executar-local.sh         # Linux/WSL
# or (Windows, needs C:\nginx):
# powershell -ExecutionPolicy Bypass -File .\scripts\executar-local.ps1
```

Brings up backend (`:8000`), KB (`:8080`), Vite (`:5173`), nginx (`:8081`).
Forces SQLite via `DATABASE_URL` override; `.env` is preserved for Docker.

### Endpoint verification

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verificar-endpoints.ps1
```

### Quality / audit scripts

```bash
bash scripts/validar_qualidade.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\executar-snapshot-qualidade-ia.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\agendar-snapshot-qualidade-ia.ps1 -Hora 8 -Minuto 0
```

Logs land in `backend/scripts_audit/logs/`.

## Conventions

- Default language for docs and UI copy is Brazilian Portuguese.
- API versioning prefix is `/v1/...` (see endpoint table in `README.md`).
- Demo login is e-mail only; role is inferred from the e-mail prefix.
- Vault fallback service name: `mvp-intelligence-vault`
  (override with `REQSYS_VAULT_SERVICE_NAME`).

## Agent guardrails

- Do not commit secrets, `.env` files, or `backend/reqsys.db` changes
  unless explicitly requested.
- Prefer editing existing docs over creating new ones; keep this file
  short and link to `README.md` / `docs/` for detail.
- When adding workflows here, verify the command exists in the repo
  (e.g. in a `package.json` script, `.sln`, or `scripts/` file) before
  documenting it. If unsure, leave a `TODO:` note instead of guessing.
