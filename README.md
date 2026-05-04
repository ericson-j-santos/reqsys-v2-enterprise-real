# ReqSys v2 Enterprise Real

> **Última atualização:** 04/05/2026 · versão `2.3.1`

## Objetivo

Solução SaaS interna para engenharia de requisitos: cadastro, backlog, histórias, rastreabilidade, auditoria e integrações corporativas.

## Stack

- Frontend: Vue 3, Vuetify, Pinia, Vue Router, Axios
- Backend: FastAPI, SQLAlchemy, Pydantic, JWT
- Banco: SQLite para demo; SQL Server configurável via `DATABASE_URL`
- Infra: Docker Compose + Nginx

## Integração opcional com o cofre local

O backend do ReqSys agora pode ler segredos do mesmo cofre local usado no MVP Intelligence.

- Prioridade de leitura: variável de ambiente primeiro, cofre local como fallback.
- Nome padrão do serviço no Credential Manager: `mvp-intelligence-vault`
- Para alterar o serviço do cofre: defina `REQSYS_VAULT_SERVICE_NAME`

Segredos suportados por fallback via cofre:

- `JWT_SECRET`
- `DATABASE_URL`
- `GITHUB_TOKEN`
- `REDMINE_BASE_URL`
- `REDMINE_API_KEY`
- `REDMINE_PROJECT_ID`
- `SSRS_BASE_URL`
- `SSRS_REPORTS_PATH`
- `SSRS_REPORT_NAMES`
- `SSRS_REQUIRE_HTTPS`

Instale as dependências do backend antes de usar o cofre:

```bash
cd backend
pip install -r requirements.txt
```

## Execução rápida

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up --build
```

## Dominios proprios (dev e prod)

### Desenvolvimento local com dominio

1. Adicione entradas no arquivo hosts do Windows:

```text
127.0.0.1 reqsys.local
127.0.0.1 api.reqsys.local
```

2. Defina no frontend (`frontend/.env`):

```text
VITE_API_URL=http://api.reqsys.local:8210
```

3. Defina no backend (`.env` na raiz):

```text
CORS_ORIGINS=http://reqsys.local:5182,http://reqsys.local:8082
```

### Producao com dominio real

1. Configure DNS (ex.: `app.seudominio.com` e `api.seudominio.com`).
2. Configure HTTPS/TLS no proxy reverso (Nginx ou balanceador).
3. Ajuste variaveis:

```text
VITE_API_URL=https://api.seudominio.com
CORS_ORIGINS=https://app.seudominio.com
```

4. Evite `allow_origins=['*']` em producao.

## Login demo

- E-mail: `ericsonjosedossantos@tieri659.onmicrosoft.com`
- Senha: `admin123`

## Endpoints principais

- `GET /health`
- `POST /v1/auth/login`
- `GET /v1/requisitos`
- `POST /v1/requisitos`
- `GET /v1/dashboard/requisitos`

## Testes automatizados

### Backend (Pytest)

```bash
cd backend
.venv\Scripts\python -m pytest
```

| Suíte              | Testes | Status     |
| ------------------ | ------ | ---------- |
| test_auth.py       | 21     | ✅ passing |
| test_requisitos.py | 17     | ✅ passing |
| test_dashboard.py  | 21     | ✅ passing |
| **Total backend**  | **59** | ✅ passing |

### Frontend — E2E Playwright

```powershell
# Pré-requisito: backend na porta 8210 e frontend na porta 5173 já em execução
cd frontend
$env:E2E_BASE_URL='http://localhost:5173'
npm run test:e2e:stable
```

| Spec               | Testes | Cobertura principal                               |
| ------------------ | ------ | ------------------------------------------------- |
| login.spec.js      | 4      | Login válido, inválido, persistência, logout      |
| dashboard.spec.js  | 6      | KPIs, cards, gráficos, navegação                  |
| relatorios.spec.js | 4      | Rota SSRS protegida, exibição, navegação via menu |
| requisitos.spec.js | 7      | CRUD, diálogo, tabela, botão novo, chip status    |
| segredos.spec.js   | 8      | Cofre, botões, tabela, card resumo, chips tooltip |
| **Total E2E**      | **30** | ✅ **30/30 passing**                              |

> O runner `test:e2e:stable` (`scripts/run-e2e-safe.js`) verifica se frontend e backend estão ativos antes de iniciar e usa `retries: 1` para absorver flakiness de rede local.

## Próximos incrementos já previstos

- SQL Server real com migrations Alembic
- Refresh token
- RBAC validado no backend por dependência FastAPI
- Integrações reais Redmine / Planner / SharePoint
- Exportação PDF/Excel
- Pipeline de CI/CD (GitHub Actions)
