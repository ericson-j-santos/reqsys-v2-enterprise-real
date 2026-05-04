# ReqSys v2 Enterprise Real

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
source .venv/bin/activate
.venv\Scripts\activate
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

## Próximos incrementos já previstos

- SQL Server real com migrations Alembic
- Refresh token
- RBAC validado no backend por dependência FastAPI
- Integrações reais Redmine / Planner / SharePoint
- Exportação PDF/Excel
- Pipeline de CI/CD
- Testes de frontend
