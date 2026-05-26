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

## Matriz de ambientes (URLs explícitas)

Status atual no repositório:

- Ambiente de desenvolvimento: criado (`docker-compose.yml` + `docker-compose.dev.yml`)
- Ambiente de produção: criado (`docker-compose.yml` + `docker-compose.prod.yml`)
- Ambiente de testes dedicado: não há arquivo `docker-compose.test.yml` neste momento
- Ambiente de testes dedicado: criado (`docker-compose.yml` + `docker-compose.test.yml`)

Use as URLs abaixo por ambiente:

| Ambiente        | URL App (Nginx)         | URL API/Docs                     | Observação                    |
| --------------- | ----------------------- | -------------------------------- | ----------------------------- |
| Desenvolvimento | `http://localhost:8083` | `http://localhost:8211/docs`     | Usa `docker-compose.dev.yml`  |
| Testes (E2E)    | `http://localhost:8084` | `http://localhost:8212/docs`     | Usa `docker-compose.test.yml` |
| Produção local  | `http://localhost:8081` | `http://localhost:8081/api/docs` | Usa `docker-compose.prod.yml` |

Importante:

- A URL `http://reqsys.localtest.me:8082` não pertence ao mapeamento atual deste projeto.
- Se desejar usar domínio local, prefira mapear para as portas ativas (`8083` em dev ou `8081` em prod).

Comandos sugeridos por ambiente:

```bash
# Desenvolvimento
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d

# Testes
docker compose -f docker-compose.yml -f docker-compose.test.yml up --build -d

# Produção local
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

### Subida automatica do Docker no Windows (Task Scheduler)

O projeto possui script para registrar a subida automatica da stack, reutilizando a logica de evitar colisao de porta do gateway.

Registrar para subir no boot da maquina:

```powershell
cd scripts
powershell -ExecutionPolicy Bypass -File .\agendar-subida-stack-docker.ps1 -TriggerType AtStartup -GatewayPort 8083
```

Registrar para subir no login do usuario:

```powershell
cd scripts
powershell -ExecutionPolicy Bypass -File .\agendar-subida-stack-docker.ps1 -TriggerType AtLogon -GatewayPort 8083
```

Registrar execucao diaria (exemplo 08:00):

```powershell
cd scripts
powershell -ExecutionPolicy Bypass -File .\agendar-subida-stack-docker.ps1 -TriggerType Daily -Hora 8 -Minuto 0 -GatewayPort 8083
```

Remover o agendamento:

```powershell
cd scripts
powershell -ExecutionPolicy Bypass -File .\agendar-subida-stack-docker.ps1 -Desagendar
```

## Mapa completo de domínios

### Domínios públicos — DuckDNS (IP: 177.121.214.69)

| Domínio | Ambiente | Porta Docker | Config nginx |
| --- | --- | --- | --- |
| `tieridev.duckdns.org` | Desenvolvimento | `:8083` | `docker-compose.dev.yml` |
| `tierin.duckdns.org` | Staging/Interno | `:8084` | `docker-compose.test.yml` |
| `tieriprod.duckdns.org` | Produção | `:8081` | `docker-compose.prod.yml` |

Todos os três domínios estão no `server_name` do `infra/nginx/default.prod.conf` e no `CORS_ORIGINS` do `.env`.

### Domínios locais — requerem entrada no `hosts`

| Domínio | Uso | Porta |
| --- | --- | --- |
| `reqsys.local` | Gateway frontend (nginx) | `:8082` / `:8083` |
| `api.reqsys.local` | Backend API direto | `:8210` |

Adicione no `C:\Windows\System32\drivers\etc\hosts`:

```text
127.0.0.1 reqsys.local
127.0.0.1 api.reqsys.local
```

### Domínios `.localtest.me` — resolvem automaticamente para 127.0.0.1

| Domínio | Porta | Uso |
| --- | --- | --- |
| `reqsys.localtest.me` | `:8081` / `:8083` | Dev/prod local com domínio amigável |
| `reqsys-test.localtest.me` | `:8084` | Testes E2E |

Não requerem entrada no `hosts` — o DNS público `*.localtest.me` resolve para `127.0.0.1`.

### Hostname de rede interna

| Host | Uso | Porta |
| --- | --- | --- |
| `NOTERI` | Servidor SSRS (SQL Server Reporting Services) | `:443` |

Configurado via `SSRS_BASE_URL=https://NOTERI:443/ReportServer` no `.env`.

### Portas por serviço

| Porta | Serviço | Ambiente |
| --- | --- | --- |
| `8081` | Gateway nginx | Produção Docker / local sem Docker |
| `8083` | Gateway nginx | Desenvolvimento Docker |
| `8084` | Gateway nginx | Testes E2E Docker |
| `8210` | Backend API (externo/debug) | Produção local |
| `8211` | Backend API (externo/debug) | Dev Docker |
| `8212` | Backend API (externo/debug) | Test Docker |
| `8000` | Backend uvicorn (interno) | Todos os modos |
| `5173` | Vite dev (frontend Vue) | Local sem Docker |
| `4200` | Angular dev | Frontend Angular |
| `8080` | KB — Knowledge Base (uvicorn) | Interno |

### Execução sem Docker (modo local)

**Linux / WSL:**
```bash
bash scripts/executar-local.sh
# Acesse: http://localhost:8081
```

**Windows (PowerShell) — requer nginx em `C:\nginx`:**
```powershell
.\scripts\executar-local.ps1
# Nginx para Windows: https://nginx.org/en/download.html
```

O script sobe automaticamente backend (`:8000`), KB (`:8080`), frontend Vite (`:5173`) e nginx (`:8081`). O `DATABASE_URL` é sobrescrito para SQLite no modo local — o `.env` com SQL Server é preservado para Docker/prod.

## Guia de uso — dia de trabalho comum

### Acesso

| Onde | URL |
| --- | --- |
| Produção (internet) | `https://tieriprod.duckdns.org` |
| Staging / interno | `https://tierin.duckdns.org` |
| Dev / local | `http://localhost:8081` |

Login: informe apenas o **e-mail** — não há senha no modo demo. O sistema determina o papel automaticamente pelo prefixo do e-mail.

| Perfil | E-mail | O que pode fazer |
| --- | --- | --- |
| **Admin** | começa com `admin` ou `ericsonjosedossantos@...` | tudo — criar, aprovar, auditar, relatórios, segredos |
| **Analista** | qualquer outro e-mail | criar requisitos, ver pipeline, rastreabilidade, specs |

---

### Rotina típica de um analista

#### 1. Abrir a aplicação e ver a situação do dia

Acesse `/` (Dashboard). Os cinco cards mostram:

- **Requisitos** — total cadastrado → clica para ir à lista
- **Em análise** — quantos estão em avaliação técnica → clica para ir ao Pipeline
- **Aprovados** — prontos para execução → clica para Rastreabilidade
- **Qualidade IA** — score do módulo de IA em percentual
- **Pendências** — itens que precisam de ação → clica para Auditoria

O **Pipeline operacional** no card lateral mostra o fluxo atual: Entrada → Normalização → Estruturação → Publicação.

---

#### 2. Registrar uma nova demanda

Vá em **Requisitos** (`/requisitos`) → botão **"Novo requisito"**.

Preencha:

- **Título** — resumo curto e objetivo (ex.: `Consulta prévia antes do cadastro rural`)
- **Urgência** — `baixa` / `media` / `alta` / `critica`
- **Descrição** — a necessidade de negócio e impacto esperado
- **Área** — área responsável ou demandante (ex.: `Crédito`)
- **Sistema** — sistema impactado (ex.: `Portal Rural`)
- **Solicitante** — usuário ou grupo que pediu (ex.: `gerencia_credito`)

Ao salvar, o requisito entra com status `recebido`.

---

#### 3. Acompanhar o fluxo de um requisito

Vá em **Pipeline** (`/pipeline`).

- **Visão Macro** — agrupa por categoria de log (visão gerencial)
- **Visão Micro** — detalha cada step individual
- **Modo demo** — ativa dados simulados para apresentação ou treinamento
- O chip de **Origem** mostra o status herdado da demanda importada

---

#### 4. Verificar rastreabilidade

Vá em **Rastreabilidade** (`/rastreabilidade`).

Cada linha da matriz mostra o encadeamento completo:

> **Requisito → História de usuário → Redmine (issue) → Planner (tarefa) → Commit → Status**

Use para responder: *"esse requisito foi implementado? em qual issue? qual commit?"*

---

#### 5. Consultar especificações de features

Vá em **Specs SDD** (`/specs`).

Sidebar esquerda lista as features do `my-first-spec-project`. Clique em uma feature para ver a especificação completa, incluindo arquivos `.sdd` vinculados.

---

#### 6. Checar a trilha de auditoria

Vá em **Auditoria** (`/auditoria`).

Linha do tempo de eventos recentes: quem criou o quê, quando e com qual `correlation_id`. Use para rastrear ações e responder perguntas de governança.

---

### Rotina adicional do administrador

**Relatórios SSRS** (`/relatorios`) — catálogo de relatórios publicados no servidor `NOTERI`. Exige `SSRS_BASE_URL` configurado no `.env`.

**Qualidade IA** (`/qualidade-ia`) — score geral, tendência e histórico do módulo de IA. Para gerar snapshot manual:

```powershell
cd scripts
powershell -ExecutionPolicy Bypass -File .\executar-snapshot-qualidade-ia.ps1
```

**Segredos** (`/segredos-status`) — diagnóstico de onde cada segredo do backend está vindo (variável de ambiente, cofre ou valor padrão). Útil para auditar configuração em produção.

---

### Status dos requisitos

| Status | Significado |
| --- | --- |
| `recebido` | demanda registrada, aguarda triagem |
| `em_analise` | em avaliação técnica/funcional |
| `aprovado` | pronto para execução |
| `rejeitado` | não aprovado — ver auditoria para motivo |

---

## Login demo

- E-mail: `ericsonjosedossantos@tieri659.onmicrosoft.com`
- Papel: `admin` (acesso total)

## Endpoints verificados (24/24 OK)

Verificados via `scripts/verificar-endpoints.ps1`. Todos passam com backend local.

### Autenticacao

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `POST` | `/v1/auth/login` | Login por e-mail; retorna JWT + papel |

### Health e Sistema

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/health` | Health check basico |
| `GET` | `/v1/sistema/info` | Versao, ambiente e configuracoes |
| `GET` | `/v1/sistema/health-check` | Health check detalhado |
| `GET` | `/v1/sistema/endpoints` | Lista de rotas registradas |
| `GET` | `/v1/sistema/segredos-status` | Origem de cada segredo (env/cofre/padrao) |

### Dashboard

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/v1/dashboard/requisitos` | KPIs de requisitos para os cards |
| `GET` | `/v1/dashboard/info` | Informacoes gerais do dashboard |

### Requisitos e Solicitacoes

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/v1/requisitos` | Lista todos os requisitos |
| `POST` | `/v1/requisitos` | Cria requisito (titulo>=5, descricao>=20 chars) |
| `POST` | `/v1/requisitos/validar` | Valida payload sem persistir |
| `POST` | `/v1/solicitacoes` | Registra solicitacao de entrada |

### Qualidade IA e Auditoria

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/v1/qualidade-ia/resumo` | Score atual e metricas |
| `GET` | `/v1/qualidade-ia/tendencia` | Historico de scores |
| `GET` | `/v1/qualidade-ia/tendencia.csv` | Historico em CSV |
| `GET` | `/v1/qualidade-ia/tendencia.pdf` | Historico em PDF |
| `POST` | `/v1/qualidade-ia/snapshot` | Gera snapshot manual |
| `GET` | `/v1/auditoria/eventos` | Trilha de auditoria |
| `GET` | `/v1/auditoria/eventos/config-infra` | Eventos de configuracao de infra |

### Cofre, Specs e Relatorios

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/v1/cofre/status` | Status do cofre local de segredos |
| `GET` | `/v1/specs` | Lista features do projeto de specs |
| `GET` | `/v1/specs/exemplos` | Exemplos de especificacoes |
| `GET` | `/v1/specs/templates` | Templates de specs disponiveis |
| `GET` | `/v1/relatorios/ssrs` | Catalogo de relatorios SSRS |
| `GET` | `/v1/relatorios/ssrs/status` | Status da conexao SSRS |
| `GET` | `/v1/relatorios/ssrs/health` | Health check do servidor SSRS |

> Rotas SSRS dependem de `SSRS_BASE_URL` configurado e servidor `NOTERI` acessivel.

### Snapshot diario (Windows Task Scheduler)

1. Gere snapshot manual quando quiser:

```powershell
cd scripts
powershell -ExecutionPolicy Bypass -File .\executar-snapshot-qualidade-ia.ps1
```

2. Agende execucao diaria automatica:

```powershell
cd scripts
powershell -ExecutionPolicy Bypass -File .\agendar-snapshot-qualidade-ia.ps1 -Hora 8 -Minuto 0
```

Os logs ficam em `backend/scripts_audit/logs/`.

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
# Pré-requisito: ambiente de testes ativo (gateway 8084 e API 8212)
cd frontend
$env:E2E_BASE_URL='http://localhost:8084'
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
