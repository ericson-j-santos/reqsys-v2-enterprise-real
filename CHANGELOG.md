# Changelog

All notable changes to this project are documented in this file.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) — [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased] - 2026-06-20

### Adicionado

- Consolidação do Runtime Operacional Autônomo Governado no `scripts/runtime_health_validator.py`, com status executivo, maturidade operacional, backlog automático, detecção de regressão, rollback governado, sincronização Fly.io e evidência navegável.
- ADR e documentação operacional do runtime em `docs/adr/ADR-034-autonomous-operational-runtime-consolidation.md` e `docs/ci/AUTONOMOUS_OPERATIONAL_RUNTIME.md`.
- Diretriz transversal de padrão ouro em `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md`.
- Varredura técnica inicial em `docs/varreduras/REQSYS_VARREDURA_PADRAO_OURO_2026-06-20.md`.
- Helper puro `frontend/src/utils/filtrosRequisitos.js` para normalização, query string e filtragem analítica de requisitos.
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
- `DashboardView.vue`: melhoria de acessibilidade por teclado nos cards interativos.
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

---

## Runtime Health Center + Operational Status Aggregator

- Adicionado agregador local `scripts/runtime_health_center.py` para consolidar status operacional por domínio (`ci_cd`, `evidence_gate`, `governance`, `runtime_risk`, `living_architecture`, `environment`, `remediation`).
- Adicionado workflow `Runtime Health Center` para gerar e publicar o artifact `runtime-health-report.json` sem rede externa, secrets ou deploy.
- Documentado o incremento no Runtime Ops Governance P1, incluindo status do padrão ouro, e adicionados testes unitários do contrato do relatório.
