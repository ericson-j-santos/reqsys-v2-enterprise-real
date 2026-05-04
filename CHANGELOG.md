# Changelog

All notable changes to this project are documented in this file.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) — [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [2.4.0] - 2026-05-04

### Adicionado

- **Módulo de Monitoramento de Qualidade de IA** no backend com endpoints:
  - `GET /v1/qualidade-ia/resumo` (score geral, métricas, contexto e recomendações)
  - `POST /v1/qualidade-ia/snapshot` (persistência de snapshot)
  - `GET /v1/qualidade-ia/tendencia` (histórico de evolução)
  - `GET /v1/qualidade-ia/tendencia.csv` (exportação da tendência em CSV)
  - `GET /v1/qualidade-ia/tendencia.pdf` (exportação da tendência em PDF)
- **Persistência de snapshots de qualidade IA** com modelo `qualidade_ia_snapshots` para análise histórica.
- **Nova tela frontend "Qualidade IA"** com:
  - score geral,
  - barras por dimensão (acurácia, relevância, consistência, segurança, cobertura),
  - tendência com sparkline,
  - recomendações acionáveis,
  - botão para geração de snapshot.
- **Novo item de navegação** no menu lateral para acesso direto ao monitoramento de IA.
- **KPI de Qualidade IA no Dashboard** principal para visibilidade executiva imediata.
- **Testes backend** em `backend/tests/test_qualidade_ia.py` cobrindo resumo, snapshot e tendência.
- **Scripts de automação** para snapshot diário:
  - `scripts/executar-snapshot-qualidade-ia.ps1`
  - `scripts/agendar-snapshot-qualidade-ia.ps1`
  - `backend/scripts_audit/gerar_snapshot_qualidade_ia.py`

### Alterado

- Versão da API FastAPI atualizada para `2.4.0`.
- Versão do frontend (`frontend/package.json`) atualizada para `2.4.0`.
- `GET /v1/sistema/info` e documentação interna agora incluem os endpoints de qualidade de IA.

---

## [2.3.1] - 2026-05-04

### Corrigido

- **CORS**: adicionadas origens `http://localhost:5174` e `http://127.0.0.1:5174` na lista de origens permitidas para compatibilidade com Vite dev server quando a porta 5173 já está em uso.

---

## [2.3.0] - 2026-05-03

### Adicionado

- **Suíte de testes de autenticação** (`backend/tests/test_auth.py`): 21 testes — login por papel (admin/analista), geração/validação de JWT, rejeição de credenciais inválidas, proteção de endpoints.
- **Suíte de testes de requisitos** (`backend/tests/test_requisitos.py`): 17 testes — CRUD completo com isolamento por usuário.
- **Suíte de testes de dashboard** (`backend/tests/test_dashboard.py`): 21 testes — métricas, status, prioridade, projetos recentes, autorização por papel.
- **Testes E2E com Playwright** (`frontend/tests/e2e/login.spec.js`): fluxo de login completo via Chromium headless.
- **Configuração Playwright** (`frontend/playwright.config.js`): baseURL `http://reqsys.localtest.me:8082`, modo headless.
- **Script `test:e2e`** em `frontend/package.json` com dependência `@playwright/test ^1.59.1`.
- **`.gitignore`**: cobertura de Python, Node, Docker e IDEs.

### Corrigido

- **Colisão UNIQUE constraint em testes** (`backend/app/api/requisitos.py`): `time()` → `time_ns()` na geração de `codigo`, eliminando falhas quando múltiplos registros são criados no mesmo segundo.
- **Bloqueio CORS no login** (`backend/app/core/config.py`, `docker-compose.yml`): origens `http://localhost:8082` e `http://reqsys.localtest.me:8082` adicionadas aos CORS permitidos.
- **Crash `crypto.randomUUID()`** (`frontend/src/services/api.js`): fallback `Math.random().toString(36)` para contextos HTTP sem Web Crypto API.
- **Aviso "password field not in form"** (`frontend/src/views/LoginView.vue`): campos envolvidos em `<form @submit.prevent>`.
- **Falha WebSocket HMR** (`frontend/vite.config.js`, `infra/nginx/default.conf`): headers `Upgrade`/`Connection` no proxy Nginx + `hmr.host`/`clientPort` explícitos no Vite.
- **404 `/favicon.ico`** (`infra/nginx/default.conf`): handler `return 204` silencioso.

### Cobertura de testes após esta versão

| Módulo              | Testes | Status     |
| ------------------- | ------ | ---------- |
| test_auth.py        | 21     | ✅ passing |
| test_requisitos.py  | 17     | ✅ passing |
| test_dashboard.py   | 21     | ✅ passing |
| **Backend total**   | **88** | ✅ passing |
| login.spec.js (E2E) | 1      | ✅ passing |

---

## [2.2.0] - 2026-05-01

### Added

- Integração com SSRS via backend (`GET /v1/relatorios/ssrs` e `GET /v1/relatorios/ssrs/health`).
- Nova tela de consumo de relatórios em `Relatórios SSRS` no frontend.
- Variáveis de ambiente para catálogos SSRS (`SSRS_BASE_URL`, `SSRS_REPORTS_PATH`, `SSRS_REPORT_NAMES`).

### Changed

- Frontend passou a usar `VITE_API_URL=/api` por padrão para suportar domínio amigável via Nginx.
- Nginx do ReqSys principal atualizado para aceitar `reqsys.localtest.me`.

### Rollback

- Para rollback do SSRS, remova `SSRS_BASE_URL` do ambiente.
- Para rollback do domínio amigável, volte `VITE_API_URL` para URL absoluta da API e mantenha acesso por localhost.

## [2.1.0] - 2026-05-01

### Added

- Integração GitHub → Redmine no pipeline do ReqSys, com busca de issues por repo, estado, limite e labels.
- Endpoint backend `POST /v1/integracoes/github/issues` para pré-visualização das issues antes da publicação.
- Publicação em lote opcional no Redmine a partir de issues do GitHub em `POST /v1/backlog/publicar-redmine/{requisito_id}`.
- UX/UI no pipeline para configurar importação GitHub, carregar issues e selecionar quais serão publicadas.
- Testes de backend para endpoint de listagem GitHub, publicação com filtro de issues e cenário com feature flag desabilitada.

### Changed

- Versão da API FastAPI atualizada para `2.1.0`.
- Fluxo de publicação no Redmine mantém compatibilidade com comportamento anterior quando a integração GitHub está desligada.

### Rollback

- Para rollback operacional sem rollback de código, definir `ENABLE_GITHUB_REDMINE_IMPORT=false`.
- Com a flag desligada, os endpoints novos retornam `409` para importação GitHub e o pipeline segue usando publicação padrão.
