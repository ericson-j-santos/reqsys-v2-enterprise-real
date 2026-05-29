# AGENTS.md

Guia rápido para agentes automatizados que trabalham neste repositório. Os comandos abaixo foram extraídos de `README.md`, `package.json` (raiz e por frontend), `.github/workflows/ci.yml`, `playwright.config.ts`, `backend-dotnet/README.md` e `scripts/`.

## Layout

- `backend/` — FastAPI + SQLAlchemy + Pydantic (Python 3.12). Testes em `backend/tests/`.
- `backend-dotnet/` — ASP.NET Core Minimal APIs (.NET 8 / C# 12). Solução `ReqSys.DotNet.sln`, testes em `backend-dotnet/tests/`.
- `frontend/` — Vue 3 + Vuetify (Vite). Frontend principal de produção.
- `frontend-vuetify/` — variante Vuetify alternativa (Vitest).
- `frontend-angular/` — variante Angular 17 (Jest).
- `e2e/` — specs Playwright multi-frontend (Vuetify e Angular).
- `scripts/` — automação local (bash + PowerShell + utilitário Python `vault_setup.py`).
- `.github/workflows/ci.yml` — pipeline de CI.

## Backend FastAPI

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload      # equivalente sem Docker: scripts/executar-local.sh
```

Testes:

```bash
cd backend
python -m pytest                   # ou: PYTHONPATH=. pytest -q
```

Variáveis usadas no CI (`backend-test`): `DATABASE_URL=sqlite:///./reqsys_test.db`, `JWT_SECRET_KEY`, `REDMINE_URL`, `REDMINE_API_KEY`, `ENABLE_GITHUB_REDMINE_IMPORT=false`, `SSRS_BASE_URL=""`. O job instala `unixodbc-dev` antes de `pip install` (dependência de `pyodbc`).

## Backend .NET / C#

```bash
cd backend-dotnet
dotnet restore ReqSys.DotNet.sln
dotnet test ReqSys.DotNet.sln
dotnet run --project src/ReqSys.Api/ReqSys.Api.csproj
```

Imagem Docker dedicada:

```bash
cd backend-dotnet
docker build -t reqsys-dotnet-api:3.1.0 .
docker run --rm -p 8080:8080 reqsys-dotnet-api:3.1.0
```

Credenciais demo do `/v1/auth/login`: `admin@reqsys.local` / `admin123`.

<!-- TODO: o backend .NET ainda não tem job dedicado em .github/workflows/ci.yml; confirmar se deve ser adicionado. -->

## Frontends

| Pasta              | Dev                                    | Build              | Testes                                                                  |
| ------------------ | -------------------------------------- | ------------------ | ----------------------------------------------------------------------- |
| `frontend/`        | `npm run dev` (Vite, host `0.0.0.0`)   | `npm run build`    | `npm run test:e2e:stable` (Playwright, runner `scripts/run-e2e-safe.js`) |
| `frontend-vuetify/`| `npm run dev` (Vite)                   | `npm run build`    | `npm run test` / `npm run test:watch` / `npm run test:coverage` (Vitest) |
| `frontend-angular/`| `npm start` (`ng serve`, porta 4200)   | `npm run build`    | `npm test` / `npm run test:coverage` (Jest)                              |

CI (`frontend-build`) usa Node 20 e roda `npm ci && npm run build` em `frontend/` com `VITE_API_URL=/api`.

## E2E na raiz (Playwright multi-frontend)

Scripts definidos em `package.json` da raiz; projetos `vuetify` (porta 5174) e `angular` (porta 4200) configurados em `playwright.config.ts`, que sobe os dois dev servers automaticamente (`webServer`).

```bash
npm run test:e2e          # playwright test
npm run test:e2e:ui       # --ui
npm run test:e2e:debug    # --debug
npm run test:e2e:report   # show-report
```

Specs atuais em `e2e/`: `login-vuetify`, `login-angular`, `accessibility-vuetify`, `accessibility-angular`.

## Stack completo via Docker

```bash
docker compose up --build                                                       # padrão (dev)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build      # ambiente de testes
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

URLs por ambiente (conforme `README.md` / `docker-compose.*.yml`):

| Ambiente        | App (Nginx)             | API/Docs                          |
| --------------- | ----------------------- | --------------------------------- |
| Desenvolvimento | `http://localhost:8083` | `http://localhost:8211/docs`      |
| Testes (E2E)    | `http://localhost:8084` | `http://localhost:8212/docs`      |
| Produção local  | `http://localhost:8081` | `http://localhost:8081/api/docs`  |

Wrapper: `scripts/publicar_ambiente.sh {dev|hml|prod}` — sobe a stack com `-d` e imprime URLs (`reqsys.local:8082` / `api.reqsys.local:8210` em dev).

## Execução local sem Docker

- `scripts/executar-local.sh` (Linux/macOS/WSL) — sobe backend (uvicorn), frontend (Vite) e, se disponível, KB e nginx como proxy reverso. Variáveis opcionais: `GATEWAY_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`, `KB_PORT`, `KB_DIR`.
- `scripts/executar-local.ps1` (Windows) — equivalente PowerShell; espera `nginx` em `C:\nginx` ou via `$env:NGINX_HOME`.

## Validação consolidada

`scripts/validar_qualidade.sh` executa, nesta ordem: `PYTHONPATH=. pytest -q` no backend, `npm run build` em `frontend-vuetify` e `frontend-angular`, e `npm run test:e2e` na raiz.

## Verificação de endpoints

- `scripts/verificar-endpoints.ps1` — varre endpoints do backend FastAPI (default `http://127.0.0.1:8000`). Aceita `-BaseUrl`, `-Email`, etc. Exit code `0` = OK, `1` = falhas.

## Cofre de segredos

- `python scripts/vault_setup.py {init|set|delete|status|import-env|gen-token}` — gerencia o cofre local compartilhado com o MVP Intelligence. Usa `app.core.secrets` do backend, então requer as dependências do backend instaladas e um `.env` legível.
- Backend lê segredo via env var primeiro, com fallback para o cofre (`REQSYS_VAULT_SERVICE_NAME` configurável; padrão `mvp-intelligence-vault`).

## Snapshot de qualidade de IA

- `python backend/scripts_audit/gerar_snapshot_qualidade_ia.py` — gera snapshot via `app.services.ai_quality.registrar_snapshot_qualidade_ia` (precisa do venv do backend ativo).
- `scripts/executar-snapshot-qualidade-ia.ps1` — wrapper Windows do snapshot manual.
- `scripts/agendar-snapshot-qualidade-ia.ps1 -Hora 8 -Minuto 0` — agenda execução diária via Task Scheduler.

## Scripts PowerShell (Windows)

- `scripts/configurar-ssrs.ps1` — configura integração SSRS.
- `scripts/reiniciar-docker-seguro.ps1`, `scripts/reiniciar-stack-limpo.ps1`, `scripts/subir-stack-sem-colisao.ps1` — utilidades de stack Docker.
- `scripts/agendar-subida-stack-docker.ps1` — agenda subida da stack via Task Scheduler (`-TriggerType AtStartup|AtLogon|Daily`, `-ExecutarAgora`, `-Desagendar`).

Logs de execução dos scripts ficam em `backend/scripts_audit/logs/`.

## Convenções para agentes

- Não comitar `backend/reqsys.db` nem artefatos gerados (`.venv/`, `node_modules/`, `dist/`, `.angular/cache/`, `bin/`, `obj/`).
- Antes de editar workflows automatizados (`.github/workflows/*`, `scripts/*`), verificar uso atual no `README.md` e neste arquivo.
- Para tarefas exclusivamente de revisão (sem mudanças), não criar nem modificar arquivos no repositório.

<!-- TODO: documentar comandos de lint/format quando forem adicionados ao repo (atualmente não há scripts de lint definidos em package.json nem hooks/configs detectados). -->
