# Living Architecture Index — ReqSys v2 Enterprise

Data de referência: 2026-06-27

Mapa navegável de módulos, fluxos, pipelines, ownership, eventos, dependências e dashboards. Complementa o JSON machine-readable em [`living-architecture-index.json`](living-architecture-index.json) e o mapa canônico em [`docs/traceability/living-architecture-map.json`](../traceability/living-architecture-map.json).

## Como navegar

| Necessidade | Seção |
| --- | --- |
| Onde estender o backend | [Módulos Backend](#módulos-backend) |
| Onde estender o frontend | [Módulos Frontend](#módulos-frontend) |
| Qual workflow usar | [Pipelines](#pipelines) |
| Quem é dono de quê | [Ownership Matrix](#ownership-matrix) |
| Eventos e contratos | [Eventos](#eventos) |
| Dependências entre camadas | [Dependências](#dependências) |
| Dashboards operacionais | [Dashboards](#dashboards) |

---

## Módulos Backend

| Módulo | Caminho | Responsabilidade | Pontos de extensão |
| --- | --- | --- | --- |
| **API** | `backend/app/api/` | 27 routers FastAPI — superfície HTTP | Novo router + `include_router` em `main.py` |
| **Core** | `backend/app/core/` | Config, security, correlation, telemetria, boot | `config.py`, `correlation.py` |
| **Services** | `backend/app/services/` | Lógica de negócio e integrações | Novo service + injeção via router |
| **Models** | `backend/app/models/` | Entidades SQLAlchemy ORM | Nova model + migration |
| **Schemas** | `backend/app/schemas/` | DTOs Pydantic | Novo schema Pydantic |
| **Middleware** | `backend/app/middleware/` | Observabilidade HTTP | `observability.py` |

### Rotas API principais

| Arquivo | Prefixo | Domínio |
| --- | --- | --- |
| `auth.py` | `/v1/auth` | Login JWT/demo, Azure |
| `requisitos.py` | `/v1/requisitos` | CRUD de requisitos |
| `agile_runtime.py` | `/v1/agile-runtime` | Sprints, work items |
| `dashboard.py` | `/v1/dashboard` | Dashboard operacional |
| `monitoramento_operacional.py` | — | Topologia, remediação |
| `runtime_analytics.py` | — | Analytics runtime durável |
| `actions_runtime_center.py` | `/v1/actions-runtime` | GitHub Actions |
| `govbi.py` | `/api/govbi` | GovBI IA |
| `rag_governado.py` | `/api/rag` | RAG governado |
| `figma_github.py` | `/v1/integracoes/figma-github` | Sync Figma ↔ GitHub e status de vínculos |
| `cofre.py` | `/v1/cofre` | Cofre local AES-GCM: init, status, gravar, remover, resolver |
| `sistema.py` | `/v1/sistema` | Diagnóstico de segredos (`/segredos-status`) |
| `webhooks.py` | `/v1/webhooks/figma` | Webhook Figma para sync bidirecional |

### Frentes de integração

| Frente | Tópico | Rota | ADR | Status |
| --- | --- | --- | --- | --- |
| Figma GitHub — retorno em tela | integração | `/figma-github` | [ADR-021](../adr/ADR-021-figma-github-retorno-em-tela.md) | implementado |
| Cofre de Segredos Locais | segurança | `/segredos-status` | [ADR-041](../adr/ADR-041-cofre-segredos-locais.md) | implementado |

Tópico Copilot Studio associado: **Sincronizar Figma GitHub** (aciona `POST /v1/integracoes/figma-github/sync` e orienta consulta em `/figma-github`).

Runbook cofre: [`docs/runbooks/cofre-operacional.md`](../runbooks/cofre-operacional.md).

---

## Módulos Frontend

| Módulo | Caminho | Responsabilidade | Pontos de extensão |
| --- | --- | --- | --- |
| **Views** | `frontend/src/views/` | 22 páginas SPA | Nova view + rota em `router/` |
| **Router** | `frontend/src/router/` | Rotas e guards RBAC | `meta.recurso` |
| **Services** | `frontend/src/services/` | Cliente HTTP | `import { api } from '../services/api'` |
| **Stores** | `frontend/src/stores/` | Estado Pinia | Nova store |
| **Components** | `frontend/src/components/` | UI reutilizável | Componentes compartilhados |
| **Auth** | `frontend/src/auth/` | Azure AD / MSAL | `azure.js`, `msal.js` |

---

## Pipelines

| Pipeline | Workflow/Script | Gates | Evidência |
| --- | --- | --- | --- |
| **CI principal** | `.github/workflows/ci.yml` | ruff, pytest, build, audit, E2E responsivo | `ci-evidence` |
| **Agent Increment Gate** | `scripts/agent_increment_gate.py` | `new_front_allowed`, gaps, duplicados | `agent-increment-gate-evidence` |
| **Living Architecture** | `living-architecture-traceability.yml` | paths, contratos | `living-architecture-traceability-report` |
| **Runtime Evidence Graph** | `runtime-operational-evidence-graph.yml` | timeline + graph JSON | `runtime-operational-evidence-graph.json` |
| **Trilhas Padrão Ouro** | `trilhas-padrao-ouro.yml` | trilhas A–E | `trilhas-padrao-ouro-evidence` |
| **Artifact Schema Validation** | `operational-artifact-schema-validation.yml` | contratos JSON | `artifact-contract-validation-report` |
| **Coordenador Status** | `coordenador-status-consolidator.yml` | artifacts 1–2 | `coordenador-status.json` |

### Categorias de workflows (~155 total)

| Categoria | Exemplos |
| --- | --- |
| CI/CD core | `ci.yml`, `ci-e2e.yml`, `ci-security.yml`, `main-smoke-ci.yml` |
| PR governance | `pr-evidence-gate`, `governed-merge-queue`, `pr-auto-recovery*` |
| Operational/runtime | `operational-*`, `runtime-*`, `reqsys-operational-health` |
| Product intelligence | `product-intelligence-*` |
| Trilhas / Living Architecture | `trilha-a`…`trilha-e`, `living-architecture-traceability` |
| Schema/governance gates | `schema-governance-gate`, `artifact-contract-validation` |

---

## Ownership Matrix

| Área | Owner | ADR de referência |
| --- | --- | --- |
| Backend API | Backend Core | [ADR-0001](../adr/ADR-0001-arquitetura-padrao-ouro.md) |
| Segurança / JWT / CORS | Security | [ADR-0002](../adr/ADR-0002-seguranca-gates-producao.md) |
| Cofre / Segredos | Security | [ADR-041](../adr/ADR-041-cofre-segredos-locais.md) |
| Ambientes dev/hml/prod | DevOps | [ADR-0003](../adr/ADR-0003-ambientes-dev-hml-prod.md) |
| CI/CD | DevOps | [ADR-0004](../adr/ADR-0004-ci-cd-qualidade.md) |
| Observabilidade | Platform Engineering | [ADR-0005](../adr/ADR-0005-observabilidade-auditoria.md) |
| Analytics drill-down | Frontend + Backend | [ADR-0006](../adr/ADR-0006-analytics-drilldown-schema-driven-ui.md) |
| Arquitetura Viva | Architecture Governance | [ADR-035](../adr/ADR-035-trilha-e-arquitetura-viva.md) |
| Trilhas Padrão Ouro | Architecture Governance | [ADR-040](../adr/ADR-040-trilhas-padrao-ouro.md) |
| Product Intelligence | Product Intelligence | [ADR-033](../adr/ADR-033-product-intelligence-final-evidence-index.md) |
| Governança PR/Agentes | Platform Engineering | [ADR-030](../adr/ADR-030-governed-dev-automerge.md) |

---

## Eventos

| Evento | Schema | Produtores | Consumidores |
| --- | --- | --- | --- |
| `product-intelligence-event` | `schemas/product-intelligence/product-intelligence-event.schema.json` | Workflows `product-intelligence-*` | Evidence navigation, executive control tower |
| `unified-operational-event` | `docs/contracts/operational-json-artifact.schema.json` | `unified-operational-event-bus.yml` | Operational intelligence hub |
| `coordenador-status` | `docs/contracts/coordenador-status.schema.json` | `coordenador-status-consolidator.yml` | Agent increment gate, `AGENTS.md` |

---

## Dependências

```text
frontend (Vite :5173)
    └── proxy /api → backend (uvicorn :8000)
            └── SQLite (reqsys.db)
workflows (.github/workflows/)
    └── valida → docs/contracts/*.schema.json
agents (Cloud Agent / Cursor)
    └── lê → docs/padrao-ouro/living-architecture-index.json
CI analytics
    └── gera → reports/github-runtime-analytics/runtime-operational-evidence-graph.json
```

---

## Dashboards

| Dashboard | Caminho | Fontes de dados |
| --- | --- | --- |
| Operational Command Center | `docs/dashboard/operational-command-center.md` | Artifact schema validation, discovery index |
| Operational Evidence Hub | `docs/dashboard/operational-evidence-hub.html` | Delivery, maturity, observability |
| Ops Dashboard | `docs/ops-dashboard/index.html` | `docs/ops-dashboard/data/health.json` |
| Trilhas Hub | `docs/architecture/trilhas/index.html` | `trilhas-registry.json` |
| Trilha E Hub | `docs/architecture/trilha-e/index.html` | `architecture-as-code.json`, diagrams |
| Live Operational Dashboard | `docs/dashboard/live-operational-dashboard.dynamic.html` | CI lead time, delivery readiness |

---

## PRs recentes e evidências

| PR | Evidências |
| --- | --- |
| [PR145](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/145) | `docs/evidence/pr145-clean-replacement-evidence.md` |
| [PR225](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/225) | `docs/evidence/pr225-evidence-navigation-ui-sync.md` |

---

## Manutenção

1. Atualizar [`living-architecture-index.json`](living-architecture-index.json) ao adicionar módulo, pipeline ou evento.
2. Atualizar [`docs/traceability/living-architecture-map.json`](../traceability/living-architecture-map.json) ao adicionar workflow, artifact ou dashboard.
3. Validar com workflow `living-architecture-traceability.yml` (report-only).
