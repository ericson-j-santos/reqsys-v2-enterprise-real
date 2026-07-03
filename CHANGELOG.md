# Changelog

All notable changes to this project are documented in this file.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) — [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased] - 2026-07-03

### Adicionado

- `RequisitosView.vue`: linhas da tabela "Analítico de requisitos" ficam clicáveis e abrem um diálogo com o detalhe completo do requisito (título, código, status, descrição, urgência, área, sistema, solicitante, impacto regulatório), usando os dados já carregados na listagem — sem chamada de rede adicional.
- `scripts/relatorio_qualidade_ia_pendentes.py`: relatório somente-leitura que lista, por ambiente (dev/hml/prod), os requisitos fora das categorias aprovado/em_analise/rejeitado — a causa raiz real do score de Qualidade IA baixo, sem mascarar ou alterar dados.
- `scripts/replicate_requisitos_anonimizado.py`: replicação on-demand (`--execute`, dry-run por padrão) de requisitos de produção para hml/dev, mascarando `solicitante` com pseudônimo estável (LGPD) e marcando origem para reexecução idempotente. Escopo deliberadamente limitado a `requisitos`; não replica `auditoria` nem `recommendation_ia`, para não contaminar a trilha de auditoria de cada ambiente.
- `.github/workflows/qualidade-ia-snapshot.yml` + `scripts/registrar_qualidade_ia_snapshot_ci.py`: snapshot diário agendado de Qualidade IA em dev/hml/prod via `POST /v1/qualidade-ia/snapshot`, com aviso automático (`::warning`) quando `score_geral < 70`.
- `docs/runbooks/qualidade-ia-e-replicacao-ambientes.md`: runbook consolidando o diagnóstico do score de Qualidade IA e o procedimento de replicação anonimizada entre ambientes.

## [Unreleased] - 2026-06-20

### Adicionado

- Application Balance Scorecard v0.1.0 em `docs/ops-dashboard/application-balance-scorecard.md` e `docs/ops-dashboard/data/application-balance-scorecard-v0.1.0.json`, consolidando domínios de equilíbrio, pesos, semáforo, evidência esperada, guardrails e caminho Pareto para estabilizar frontend, runtime, API, CI/CD, governança, documentação e segurança.
- Operational Evidence Hub em `docs/dashboard/operational-evidence-hub.html` consolidando delivery readiness, completion, finalization, maturity snapshot, observability correlation, artifact contract validation, dashboard regression validation e living architecture traceability com cards executivos, drill-down navegável, semáforo, confidence level, operational risk e fallback governado para artifacts ausentes.
- Runbook `docs/runbooks/operational-evidence-hub.md` e atualização dos índices de rastreabilidade (`living-architecture-map.json`, `command-center-evidence-index.md`, `command-center-navigation-map.md`, `operational-command-center.md`).
- Validação estática ampliada em `scripts/validate-dashboard-regression.mjs` para o Evidence Hub (cards, fontes JSON, drill-down, fallback e indicadores de governança).

- REQSYS#326: Runtime Observability Foundation com correlation analytics, topology preview, readiness de observabilidade e artifacts lógicos `runtime-correlation-report.json`/`runtime-observability-report.json` nos endpoints runtime.
- REQSYS#325: Smoke validator público com `ops-readiness-report.json`, validação opcional de frontend/runtime dashboard/incidentes/CORS, readiness consolidado e integração do status Fly/DuckDNS ao Ops Dashboard.
- REQSYS#323: Ops Dashboard com drill-down por domínio, detalhes de health/evidence/risk/environment drift/governance, Incident Timeline local filtrável e integração opcional de `runtime-health-report.json` e `runtime-operational-evidence-graph.json`.
- Runtime Health Center P2 (`schema_version=1.1.0`) com ingestão local de artifacts, consolidação de evidence graph/risk scoring/PR Evidence Gate e detector de drift entre dev/test/prod refletido em `maturity_percent` e `operational_risk`.
- Consolidação do Runtime Operacional Autônomo Governado no `scripts/runtime_health_validator.py`, com status executivo, maturidade operacional, backlog automático, detecção de regressão, rollback governado, sincronização Fly.io e evidência navegável.
- Runtime Health Validator `schema_version=1.2.0`: health matrix, runtime score canônico, quarantine (`AOP-SEC-QUARANTINE-001`), retry policy governada (`AOP-CI-RETRY-001`), fallback progressivo (API → cache → baseline) e propagação de `runtime_score` no Coordenador Status Consolidator.
- ADR e documentação operacional do runtime em `docs/adr/ADR-034-autonomous-operational-runtime-consolidation.md` e `docs/ci/AUTONOMOUS_OPERATIONAL_RUNTIME.md`.
- Diretriz transversal de padrão ouro em `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md`.
- Varredura técnica inicial em `docs/varreduras/REQSYS_VARREDURA_PADRAO_OURO_2026-06-20.md`.
- Helper puro `frontend/src/utils/filtrosRequisitos.js` para normalização, query string e filtragem analítica de requisitos.
- Helper puro `frontend/src/utils/filtrosIntegracao.js` para drill-down analítico do Painel de Integrações (origem, status, data, correlation_id e busca).
- Helpers `filtrosGovbi.js`, `filtrosPipeline.js` e `filtrosTaskConsole.js` com testes unitários para drill-down analítico; GovBI inclui `calcularMetricasGovbi` e `exportarEvidenciaGovbi`.
- Constante `frontend/src/constants/rotasResponsivas.js` com as 16 rotas operacionais canônicas para validação responsiva.
- Helper E2E `tests/e2e/helpers/responsiveMocks.js` para mocks estáveis das 16 rotas.
- Teste unitário `frontend/src/utils/filtrosIntegracao.test.js` para filtros analíticos de integrações.
- Teste unitário `frontend/src/utils/filtrosRequisitos.test.js` para filtros analíticos de requisitos.
- Script `npm run test:unit` no frontend.
- Painel runtime de Connection Broker em `frontend/src/views/MonitoramentoOperacionalView.vue`, com cards, analítico, fallback seguro e consumo futuro de `/api/connectors/health`.
- Contrato técnico dos endpoints `/api/connectors/health` e `/api/connectors/capabilities/check` em `docs/api/connection-broker-runtime-contract.md`.
- Backend .NET inicial do Connection Broker com `GET /api/connectors/health`, `POST /api/connectors/capabilities/check` e aliases versionados em `/v1/connectors/*`.
- Testes xUnit cobrindo shape do health-check e bloqueio governado de escrita em produção.
- Registry em memória do Connection Broker no `ReqSysStore`, com capabilities por ambiente, status, criticidade e necessidade de confirmação humana.
- Auditoria operacional para `connection_broker.capability_check` com `correlation_id` rastreável.
- Teste xUnit validando que a validação de capability registra trilha de auditoria com `correlation_id`.
- Registry persistente versionado em `backend-dotnet/src/ReqSys.Api/config/connectors/connection-broker-registry.json`.
- Carga configurável do registry via variável `REQSYS_CONNECTION_BROKER_REGISTRY`, com fallback governado em memória quando o arquivo não estiver disponível ou for inválido.
- Teste xUnit validando carga do registry JSON e auditoria de carregamento.

### Alterado

- `DashboardView.vue`: cards de requisitos agora apontam para rotas analíticas com filtros por query string quando aplicável.
- `DashboardView.vue`: card de erros de integração com drill-down para `/painel-integracao?status=erro`.
- `DashboardView.vue`: melhoria de acessibilidade por teclado nos cards interativos.
- `PainelIntegracaoView.vue`: analítico filtrável por origem, status, data, correlation_id e busca textual, com cards clicáveis e sincronização de query string.
- `GovBIView.vue`: histórico analítico padrão ouro com métricas clicáveis (total, sucesso, degradado, latência média), filtro de fallback, exportação de evidência JSON, `filter-grid`/`responsive-table-shell`, query string e **painel permanente de funcionamento** com testes locais + API exibidos sempre na tela.
- `govbiFuncionamento.js` e endpoint `GET /api/govbi/funcionamento` para auto-teste com percentual 100%.
- `PipelineView.vue`: histórico de execuções com analítico por etapa, duração, status e correlation_id.
- `TaskConsoleView.vue`: filtros analíticos de tarefas e histórico de envios ao Planner com query string.
- `DashboardView.vue`: cards de drill-down para GovBI degradado, pipeline com erro e Task Console pendente.
- `styles.css`: utilitários responsivos globais (`.page-actions`, `.filter-grid`, shells de tabela) para Hub, GovBI, Task Console e demais telas.
- `data-testid` nas 16 rotas operacionais para validação E2E de responsividade.
- `tests/e2e/responsividade.spec.js`: cobertura das 16 rotas em mobile, tablet e desktop sem overflow horizontal.
- `MonitoramentoOperacionalView.vue`: expansão para incluir indicadores de conectores, criticidade, ações sugeridas e `correlation_id`.
- `ReqSysEndpoints.cs`: módulo `connection-broker` passa a constar em `/v1/sistema/info`.
- `ReqSysEndpoints.cs`: endpoints do Connection Broker deixam de usar payload estático local e passam a consumir o registry do `ReqSysStore`.
- `ReqSys.Api.csproj`: registry JSON passa a ser copiado para o output da aplicação.

### Pendente

- A atualização completa de `RequisitosView.vue` para consumir os filtros por query string foi bloqueada pelo conector de escrita durante este ciclo. Deve ser tratada em PR técnico específico, mantendo a lógica já isolada em `filtrosRequisitos.js`.
- Evoluir o Connection Broker para health-check real por provedor e exportação de métricas.
- Persistir auditoria em storage durável externo ao processo.

### Ambiente

- Ambiente observado: GitHub / branch `main`.
- Ambiente de aplicação: branch `feature/connection-broker-registry-file`.
- Produção: sem alteração direta.

---

## [3.1.0] - 2026-05-28

### Adicionado

- REQSYS#323: Ops Dashboard com drill-down por domínio, detalhes de health/evidence/risk/environment drift/governance, Incident Timeline local filtrável e integração opcional de `runtime-health-report.json` e `runtime-operational-evidence-graph.json`.
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

- REQSYS#323: Ops Dashboard com drill-down por domínio, detalhes de health/evidence/risk/environment drift/governance, Incident Timeline local filtrável e integração opcional de `runtime-health-report.json` e `runtime-operational-evidence-graph.json`.
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

---

## Runtime Health Center + Operational Status Aggregator

- Adicionado agregador local `scripts/runtime_health_center.py` para consolidar status operacional por domínio (`ci_cd`, `evidence_gate`, `governance`, `runtime_risk`, `living_architecture`, `environment`, `remediation`).
- Adicionado workflow `Runtime Health Center` para gerar e publicar o artifact `runtime-health-report.json` sem rede externa, secrets ou deploy.
- Documentado o incremento no Runtime Ops Governance P1, incluindo status do padrão ouro, e adicionados testes unitários do contrato do relatório.
