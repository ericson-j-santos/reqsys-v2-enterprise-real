# Changelog

All notable changes to this project are documented in this file.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) — [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [3.1.0] - 2026-05-28

### Adicionado

- Versionamento canônico em `VERSION` antes do desenvolvimento da nova aplicação.
- Documentação GitFlow em `docs/GITFLOW.md`, com branches, checklist de release, convenção de commits e fluxo de tag.
- Aplicação inicial completa em .NET 8/C# em `backend-dotnet/`, com solution, projeto ASP.NET Core Minimal API, Dockerfile, README e testes xUnit.
- Módulos .NET entregues: autenticação, saúde, sistema, dashboard, requisitos CRUD, pipeline, relatórios, auditoria e qualidade IA.

### Alterado

- README atualizado para declarar a versão `3.1.0` e a nova stack .NET/C# em evolução.
- API FastAPI existente alinhada para versão `3.1.0` e compatibilidade dos testes de autenticação/diagnóstico de segredos.
- Metadados de versão dos assemblies .NET centralizados em `backend-dotnet/Directory.Build.props`.
- `.gitignore` atualizado para ignorar banco local de testes na raiz e permitir rastrear a solution .NET em `backend-dotnet/`.

### Testado

- Conferência estática dos artefatos C# criados e dos arquivos de versionamento.
- Teste automatizado .NET documentado em `backend-dotnet/tests/ReqSys.Api.Tests`; execução local bloqueada no ambiente atual porque o SDK `dotnet` não está instalado.

### Rollback

- Remover o diretório `backend-dotnet/`, reverter `VERSION`, `README.md`, `CHANGELOG.md` e `docs/GITFLOW.md` para retornar ao backend FastAPI como única implementação ativa.

---

## [2.8.0] - 2026-05-15

### Adicionado

- **Integração completa com Redmine Wiki Sync service**
  - ReqSys agora publica documentação de requisitos nas páginas Wiki do Redmine via serviço dedicado (`redmine-wiki-sync-enterprise-v9`) com fila RabbitMQ e worker assíncrono
  - `POST /v1/wiki/requisitos/{id}/publicar` — publica um requisito na Wiki
  - `GET  /v1/wiki/requisitos/{id}/status` — consulta status de sincronização
  - `POST /v1/wiki/requisitos/publicar-lote` — publica todos os requisitos em lote

- **Verificação de versão no GitHub antes de publicar**
  - Antes de qualquer publicação, o ReqSys consulta o GitHub para verificar se já existe uma versão do arquivo
  - Se conteúdo for **idêntico** → publicação ignorada (evita sobrescrita desnecessária)
  - Se conteúdo for **divergente** → publicação bloqueada com alerta; use `forcar_atualizacao=true` para forçar
  - Se arquivo **não encontrado** → publicação prossegue normalmente criando a página
  - Status retornados: `sincronizado`, `divergente`, `nao_encontrado`, `verificacao_desabilitada`, `erro`

- **Gate de pré-validação operacional** (`POST /v1/processos/pre-validar`, `POST /v1/processos/iniciar`)
  - Valida campos obrigatórios, RBAC por escopo, evidências, regras por tipo e score de prontidão (0–100)
  - Tipos suportados: `demanda`, `servico`, `dossie`

- **RBAC expandido**: escopos `demanda:iniciar/cancelar/aprovar/arquivar`, `servico:executar/cancelar/aprovar`, `dossie:criar/iniciar/aprovar/arquivar` e novo perfil `gestor`

- **Novos arquivos**:
  - `app/services/wiki_publisher.py` — orquestra geração de conteúdo Markdown, verificação GitHub e chamada ao Wiki Sync
  - `app/services/github_version_checker.py` — verifica e compara versão de arquivos no GitHub via API REST
  - `app/schemas/wiki.py` — modelos `PublicarWikiRequest`, `PublicarWikiResult`, `GitHubVersionStatus`, `WikiStatusResult`
  - `app/schemas/processos.py` — modelos `ContextoAntecipacao`, `ResultadoAntecipacao`, `ItemValidacao`, `TipoProcesso`, `Severidade`
  - `app/services/prontidao.py` — lógica de `antecipar_validacoes()` e funções de validação por tipo
  - `app/api/wiki.py` — router `/v1/wiki`
  - `app/api/processos.py` — router `/v1/processos`

### Alterado

- Versão da API: `2.6.0` → `2.8.0`
- `app/core/config.py`: novas variáveis `WIKI_SYNC_BASE_URL`, `WIKI_SYNC_TOKEN`, `GITHUB_DOCS_REPO`, `GITHUB_DOCS_BASE_PATH`, `app_version`
- `app/services/rbac.py`: escopos completos e perfil `gestor`

### Variáveis de ambiente — novas em 2.8.0

```env
# Redmine Wiki Sync service (obrigatório para publicação na Wiki)
WIKI_SYNC_BASE_URL=http://localhost:5000
WIKI_SYNC_TOKEN=<jwt-token-com-scope-wiki.write>

# Verificação de versão no GitHub (opcional, aumenta segurança)
GITHUB_DOCS_REPO=owner/repo
GITHUB_DOCS_BASE_PATH=docs/requisitos
GITHUB_TOKEN=<github-pat>
```

---

## [2.7.0] - 2026-05-06

### Adicionado

- **Design Tokens Institucionais** — `PADRAO_VISUAL_INSTITUCIONAL.md` com paleta oficial (Primary #005CA9, Secondary #F39200, Tertiary #00B3AD), tipografia e espaçamento.
- **Theming institucional aplicado** em todos os frontends (Vuetify 3 + Angular Material): variáveis CSS atualizadas em conformidade com os tokens.
- **`InstitucionalStatusBannerComponent` (Angular)** — componente reutilizável para estados `loading | error | warning | info | success | empty` com `aria-live`, `role` semântico e suporte a callback `onRetry`. Integrado nas 7 telas Angular.
- **Composable `useStatusBanner` (Vue 3)** — `frontend-vuetify/src/composables/useStatusBanner.js`; provê `loading`, `errorMessage`, `warningMessage`, `setLoading()`, `setError()`, `setWarning()`, `clearAll()`; implementa paridade arquitetural com o componente Angular.
- **Dashboard Angular** — `DashboardComponent` completo com signals/computed, KPI cards navegáveis (`.clickable`/`.metric-nav`), SCSS com hover transform e focus-visible acessível.

### Alterado

- **6 views Vuetify** (`RastreabilidadeView`, `AuditoriaView`, `SegredosStatusView`, `QualidadeIAView`, `RelatoriosView`, `PipelineView`) — refs locais de estado `loading`/`errorMessage` substituídas por destructuring do composable `useStatusBanner`; funções de carga/ação usam `setLoading()` e `setError()` em vez de atribuição direta.
- **Bundle Vuetify otimizado** — `vite-plugin-vuetify` tree-shaking ativo; `manualChunks` segmentando `vuetify-vendor`, `vue-vendor`, `icons-vendor`, `http-vendor`; build sem chunk warnings.
- **UX microinterações padronizadas** em todas as telas (Vuetify + Angular): hover, foco visível, aria-live para feedback assíncrono.
- **Acessibilidade ARIA** — `aria-live="polite"` e `aria-live="assertive"` em todos os banners de estado nas 6 telas Angular.

### Corrigido

- **`frontend-vuetify/src/views/PipelineView.vue`** — `errorMessage.value = ''` redundante removido de `resetFlow()` e `runPipeline()`; catch substituído por `setError()`.
- **`frontend-vuetify/src/views/RelatoriosView.vue`** — `errorMessage.value = ''` redundante removido de `downloadPdf()` e `loadStatus()`; catch substituído por `setError()`.
- **`frontend-vuetify/src/views/QualidadeIAView.vue`** — `createSnapshot()`, `exportCsv()`, `exportPdf()` atualizados para usar `setError()` do composable.
- **`frontend-angular/src/app/views/dashboard/dashboard.component.scss`** — adicionados `.clickable` e `.metric-nav` com `cursor: pointer`, `user-select: none`, hover `translateY(-2px)` e `focus-visible` acessível.

---

## [2.6.0] - 2026-05-06

### Adicionado

- **Testes unitários frontend-vuetify** — Vitest + @vue/test-utils: specs para `LoginView`, `auth.spec.js`, `router.spec.js`; script `test`, `test:watch`, `test:coverage` em `package.json`; configuração `test` embutida no `vite.config.js`.
- **Testes unitários frontend-angular** — Jest + jest-preset-angular: `jest.config.ts`, `tsconfig.spec.json`, `setup-jest.ts`; specs para `AuthService`, `AuthInterceptor`, `AuthGuard`, `LoginComponent`; scripts `test` e `test:coverage`.
- **Testes E2E Playwright** — `playwright.config.ts` na raiz; suíte `e2e/` cobrindo fluxo de login end-to-end.
- **Checklist operacional** — `CHECKLIST_OPERACIONAL_ATUALIZACAO_CONTINUA.md` com protocolo de diagnóstico, criação, validação e governança.

### Corrigido

- **backend/relatorios.py**: `_get_ssrs_auth()` agora lança `HTTPException(503)` (em vez de `RuntimeError`) quando SSPI não está disponível e credenciais não estão configuradas — garante resposta HTTP controlada em Linux/CI.
- **frontend-angular/app.routes.ts**: nome do componente corrigido de `QualidadeIAComponent` para `QualidadeIaComponent` (case-sensitive export).

### Alterado

- **docker-compose.yml**: removidos `container_name` fixos dos serviços `api`, `frontend`, `kb` e `nginx` para facilitar execução de múltiplas instâncias e evitar conflitos de nome.
- **frontend-vuetify/vite.config.js**: adicionado bloco `test` (Vitest) com ambiente `jsdom`, globals, cobertura `v8`.
- **frontend-angular/package.json**, **frontend-vuetify/package.json**: dependências de teste adicionadas (`jest`, `jest-preset-angular`, `ts-node`, `vitest`, `@vue/test-utils`, `jsdom`, `@vitest/coverage-v8`).

---

## [2.5.0] - 2026-05-05

### Adicionado

- **Frontend Vue 3 / Vuetify 3** (`frontend-vuetify/`) — scaffold completo com:
  - Tema escuro personalizado `reqsysDark` (bg `#0d1117`, primary amber `#fbbf24`).
  - Autenticação JWT, Pinia store, Vue Router 4 com lazy loading e guards.
  - Interceptor Axios com `X-Correlation-Id` automático e fallback para contextos HTTP.
  - 8 views: Login, Dashboard, Requisitos, Pipeline, Qualidade IA, Relatórios, Segredos Status, Rastreabilidade, Auditoria.
  - Proxy Vite (`/api` → `localhost:8081`), porta 5174.
- **Frontend Angular 17 / Angular Material** (`frontend-angular/`) — scaffold completo com:
  - Tema escuro Angular Material: amber primary, indigo accent.
  - Standalone components, lazy loading por rota, `CanActivateFn` guard.
  - Interceptor HTTP funcional com `X-Correlation-Id` e fallback de `crypto.randomUUID()`.
  - Sidenav responsivo com rail mode (desktop) e overlay (mobile) via `BreakpointObserver`.
  - 8 views: Login, Dashboard, Requisitos (tabela reativa com filtros), + 6 stubs.
  - Proxy `proxy.conf.json` (`/api` → `localhost:8081`), porta 4200.
- Credenciais de demonstração documentadas no README de cada frontend.

---

## [2.4.1] - 2026-05-05

### Adicionado

- Filtro de período (7d / 30d / 90d / Todos) nos endpoints de exportação CSV e PDF de qualidade IA via query param `?dias=`.
- `dias` query param (opcional, 1–365) nos endpoints `GET /v1/qualidade-ia/tendencia`, `/tendencia.csv` e `/tendencia.pdf`.
- Seletor de período (`v-btn-toggle`) na view Qualidade IA com atualização automática da tendência.
- 3 novos testes unitários cobrindo filtro de período nas exportações e no payload de tendência.

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
