# Contract Catalog — Inventário de Contratos

Data de referência: 2026-06-27

Inventário centralizado de **schemas, eventos, APIs, payloads, outputs e pipelines** do ReqSys. Objetivo: evitar quebra silenciosa entre incrementos paralelos.

## Como usar

| Situação | Ação |
| --- | --- |
| Novo artifact JSON | Definir schema em `docs/contracts/` + registrar aqui |
| Novo evento de domínio | Registrar em Schema Registry + Contract Catalog |
| Validar compatibilidade | `operational-artifact-schema-validation.yml` |
| Quebra de contrato | Major version + ADR |

## Registros centrais

| Registro | Caminho | Escopo |
| --- | --- | --- |
| **Schema Registry** | [`docs/schema-registry.json`](../schema-registry.json) | Schemas com gates de validação (semver, breaking change) |
| **Artifact Contracts Index** | [`docs/contracts/artifact-contracts-index.md`](../contracts/artifact-contracts-index.md) | Inventário completo de artifacts JSON (~190 entradas) |
| **Living Architecture Map** | [`docs/traceability/living-architecture-map.json`](../traceability/living-architecture-map.json) | Schemas declarados no mapa de rastreabilidade |

---

## Schemas operacionais (`docs/contracts/`)

### Governança e coordenação

| Schema | Arquivo | Domínio | Status |
| --- | --- | --- | --- |
| agent-output | `agent-output.schema.json` | ai-governance | active |
| coordenador-status | `coordenador-status.schema.json` | governance | active |
| living-architecture-map | `living-architecture-map.schema.json` | traceability | active |
| trilhas-padrao-ouro | `trilhas-padrao-ouro.schema.json` | governance | active |
| contract-validation-report | `contract-validation-report.schema.json` | governance | active |
| artifact-contract-validation-report | `artifact-contract-validation-report.schema.json` | governance | active |

### Trilhas (A–E)

| Schema | Arquivo | Trilha |
| --- | --- | --- |
| trilha-a-runtime-publico | `trilha-a-runtime-publico.schema.json` | A — Runtime Público |
| trilha-b-observabilidade-enterprise | `trilha-b-observabilidade-enterprise.schema.json` | B — Observabilidade |
| trilha-c-ux-operacional | `trilha-c-ux-operacional.schema.json` | C — UX Operacional |
| trilha-d-qualidade-governanca | `trilha-d-qualidade-governanca.schema.json` | D — Qualidade |
| trilha-e-arquitetura-viva | `trilha-e-arquitetura-viva.schema.json` | E — Arquitetura Viva |

### Camada de testes (Tier 1)

| Schema | Arquivo | Uso |
| --- | --- | --- |
| camada-testes-padrao-ouro | `camada-testes-padrao-ouro.schema.json` | Relatório do validador da camada de testes |

### Delivery e release

| Schema | Arquivo | Uso |
| --- | --- | --- |
| delivery-evidence-report | `delivery-evidence-report.schema.json` | Evidências de CI |
| delivery-readiness-report | `delivery-readiness-report.schema.json` | Prontidão de entrega |
| delivery-status-report | `delivery-status-report.schema.json` | Status de delivery |
| delivery-burndown-snapshot | `delivery-burndown-snapshot.schema.json` | Burndown executivo |
| delivery-completion-snapshot | `delivery-completion-snapshot.schema.json` | Snapshot de conclusão |
| delivery-finalization-report | `delivery-finalization-report.schema.json` | Finalização |
| delivery-maturity-snapshot | `delivery-maturity-snapshot.schema.json` | Maturidade |
| release-readiness | `release-readiness.schema.json` | Prontidão de release |

### Operações e analytics

| Schema | Arquivo | Uso |
| --- | --- | --- |
| operational-json-artifact | `operational-json-artifact.schema.json` | **Contrato base** para artifacts sem schema específico |
| operational-artifact-discovery-index | `operational-artifact-discovery-index.schema.json` | Índice de descoberta |
| operational-history-index | `operational-history-index.schema.json` | Índice de histórico |
| operational-history-snapshot | `operational-history-snapshot.schema.json` | Snapshot de histórico |
| operational-maturity-score | `operational-maturity-score.schema.json` | Score de maturidade |
| observability-correlation-report | `observability-correlation-report.schema.json` | Correlação observabilidade |
| runtime-predictive-analytics | `runtime-predictive-analytics.schema.json` | Analytics preditivo |
| ci-lead-time-analytics | `ci-lead-time-analytics.schema.json` | Lead time de CI |
| command-center-readiness | `command-center-readiness.schema.json` | Prontidão command center |

---

## Eventos de domínio

| Evento | Schema | Produtores | Consumidores |
| --- | --- | --- | --- |
| product-intelligence-event | `schemas/product-intelligence/product-intelligence-event.schema.json` | Workflows PI | Evidence navigation, executive tower |
| unified-operational-event | `operational-json-artifact.schema.json` | `unified-operational-event-bus.yml` | Operational intelligence |
| coordenador-status | `coordenador-status.schema.json` | `coordenador-status-consolidator.yml` | Agent increment gate |

---

## APIs internas (backend)

| Prefixo | Router | Contrato |
| --- | --- | --- |
| `/v1/auth` | `auth.py` | JWT (issuer, audience, exp) — ver ADR-0002 |
| `/v1/requisitos` | `requisitos.py` | Pydantic schemas em `backend/app/schemas/` |
| `/v1/agile-runtime` | `agile_runtime.py` | Agile runtime schemas |
| `/v1/dashboard` | `dashboard.py` | Dashboard payloads |
| `/v1/auditoria` | `auditoria.py` | Auditoria com correlation_id |
| `/monitoramento-operacional` | `operational_intelligence.py` | Operational health dashboard schema |
| `/api/govbi` | `govbi.py` | GovBI IA |
| `/api/rag` | `rag_governado.py` | RAG governado — ver `docs/ai-governance/05-DADOS/RAG_STANDARD.md` |
| `/v1/integracoes/figma-github` | `figma_github.py` | Sync Figma ↔ GitHub (`POST /sync`, `GET /status`) |
| `/v1/webhooks/figma` | `webhooks.py` | Webhook Figma (assinatura `X-Figma-Signature`) |
| `/v1/cofre` | `cofre.py` | Cofre local AES-GCM — ver [ADR-041](../adr/ADR-041-cofre-segredos-locais.md) |
| `/v1/sistema` | `sistema.py` | Diagnóstico de segredos (`GET /segredos-status`) |
| `/v1/codex` | `codex_governado.py` | Análise governada com LLM — ver ADR-023, ADR-024 |

### Frentes de integração registradas

| ID | Frente | Tópico | Feature flag |
| --- | --- | --- | --- |
| `figma-github` | Figma GitHub — retorno em tela | integração | `ENABLE_FIGMA_GITHUB_SYNC` |
| `cofre-segredos` | Cofre de Segredos Locais | segurança | `REQSYS_VAULT_SERVICE_NAME`, `VAULT_API_TOKEN` |
| `codex-governado` | Codex VS Code/LLM Local + Online | IA · codificação | `CODEX_OLLAMA_BASE_URL`, `CODEX_OLLAMA_MODEL` |

### Contrato Codex (`/v1/codex`)

| Endpoint | Auth | Request | Response `data` |
| --- | --- | --- | --- |
| `POST /analyze` | JWT | `{ provider, contexto, entrada, correlation_id?, publicar_no_reqsys? }` | Resultado com `correlation_id`, `resumo`, `reqsys_payload` |
| `GET /status` | JWT | — | `{ servico, providers, guard_rails }` |
| `GET /operational-summary` | JWT | `?limite=10` | `{ dashboard: { total, bloqueados, latencia_media, ... } }` |

Providers: `mock`, `ollama`, `openai`, `claude`. Runbook: [`docs/runbooks/codex-vscode-local-inicio-rapido.md`](../runbooks/codex-vscode-local-inicio-rapido.md).


### Contrato Cofre (`/v1/cofre`)

| Endpoint | Auth | Request | Response `data` |
| --- | --- | --- | --- |
| `POST /init` | JWT admin | `?overwrite=false` | `{ status, service }` |
| `GET /status` | JWT admin | — | `{ inicializado, service, vault_api_token_configurado }` |
| `POST /segredos` | JWT admin | `{ key, value }` | `{ key, gravado }` |
| `DELETE /segredos/{key}` | JWT admin | — | `{ key, removido }` |
| `GET /segredos/{key}` | `X-Vault-Token` | — | `{ key, value }` |
| `POST /resolver` | `X-Vault-Token` | `{ key }` | `{ key, value }` |

Diagnóstico (`GET /v1/sistema/segredos-status`): cada item contém `name`, `source` (`env|vault|default|absent`), `configured`, `resolved`, `value_exposed: false`.

Chave reservada bloqueada: `__master_key__`.

Runbook: [`docs/runbooks/cofre-operacional.md`](../runbooks/cofre-operacional.md).

### Contrato frontend ↔ backend

| Item | Contrato |
| --- | --- |
| Proxy dev | `frontend/vite.config.js` — `/api` → `127.0.0.1:8000` |
| Cliente HTTP | `frontend/src/services/api.js` — `export const api` (import nomeado) |
| Auth | Token em `data.access_token` (login demo) |

---

## Contrato mínimo de artifact operacional

Todo artifact JSON operacional deve convergir para:

```json
{
  "generated_at": "ISO-8601",
  "source": "workflow-name",
  "status": "ok|warning|error",
  "confidence_level": "high|medium|low",
  "maturity_percent": 0-100,
  "operational_risk": "low|medium|high|critical",
  "commit_sha": "abc123",
  "workflow_run_id": "optional"
}
```

Definido em `operational-json-artifact.schema.json`.

---

## Pipelines de validação

| Pipeline | Workflow | Modo |
| --- | --- | --- |
| Artifact Contract Validation | `artifact-contract-validation.yml` | report-only |
| Operational Artifact Schema Validation | `operational-artifact-schema-validation.yml` | report-only |
| Schema Governance Gate | `schema-governance-gate.yml` | enforced |
| Schema Runtime Validation | `schema-runtime-validation.yaml` | enforced |
| Extended Contract Validation | `extended-operational-contract-validation.yml` | report-only |

---

## Política de evolução

1. **Breaking change** → major version no schema + ADR.
2. **Novo campo opcional** → minor version.
3. **Correção de documentação/exemplo** → patch version.
4. Todo schema novo deve ter pelo menos um exemplo válido.
5. Registrar no Schema Registry (`docs/schema-registry.json`).
6. Atualizar Artifact Contracts Index quando o artifact for inventariado.

## Referências

- Hub Tier 1: [`docs/padrao-ouro/README.md`](README.md)
- Runbook validação: [`docs/runbooks/operational-artifact-schema-validation.md`](../runbooks/operational-artifact-schema-validation.md)
- Connection Broker: [`docs/api/connection-broker-runtime-contract.md`](../api/connection-broker-runtime-contract.md)
- Ops Dashboard contracts: [`docs/ops-dashboard/contracts/`](../ops-dashboard/contracts/)
