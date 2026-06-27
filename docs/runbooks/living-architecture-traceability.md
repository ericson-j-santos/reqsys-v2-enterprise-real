# Runbook — Living Architecture Traceability

## Objetivo

Manter um índice vivo e navegável que conecte workflows, artifacts, contratos, dashboards, runbooks, PRs recentes e evidências de CI sem alterar runtime ou deploy.

## Índice canônico machine-readable

| Item | Caminho | Uso |
|---|---|---|
| Mapa vivo | [`docs/traceability/living-architecture-map.json`](../traceability/living-architecture-map.json) | Fonte canônica navegável para automações e revisão humana. |
| Schema do mapa | [`docs/contracts/living-architecture-map.schema.json`](../contracts/living-architecture-map.schema.json) | Contrato mínimo do índice de rastreabilidade. |
| Workflow de validação | [`.github/workflows/living-architecture-traceability.yml`](../../.github/workflows/living-architecture-traceability.yml) | Validação report-only de links internos e artifacts sem contrato. |

## Navegação por domínio

### Workflows

- [CI principal](../../.github/workflows/ci.yml) — gate base de validação de backend, frontend, segurança e evidências.
- [Operational Artifact Schema Validation](../../.github/workflows/operational-artifact-schema-validation.yml) — valida contratos de artifacts operacionais.
- [Operational Artifact Discovery Index](../../.github/workflows/operational-artifact-discovery-index.yml) — indexa artifacts operacionais publicados.
- [Living Architecture Traceability](../../.github/workflows/living-architecture-traceability.yml) — report-only para links internos e contratos de artifacts declarados.

### Artifacts e contratos

| Artifact lógico | Contrato | Consumidores |
|---|---|---|
| `operational-artifact-schema-validation` | [`docs/contracts/contract-validation-report.schema.json`](../contracts/contract-validation-report.schema.json) | [`docs/dashboard/operational-command-center.md`](../dashboard/operational-command-center.md) |
| `operational-artifact-discovery-index` | [`docs/contracts/operational-artifact-discovery-index.schema.json`](../contracts/operational-artifact-discovery-index.schema.json) | [`docs/dashboard/operational-command-center.md`](../dashboard/operational-command-center.md) |
| `ci-evidence` | [`docs/contracts/delivery-evidence-report.schema.json`](../contracts/delivery-evidence-report.schema.json) | [`docs/dashboard/command-center-evidence-index.md`](../dashboard/command-center-evidence-index.md) |
| `living-architecture-traceability-report` | [`docs/contracts/living-architecture-map.schema.json`](../contracts/living-architecture-map.schema.json) | [`docs/dashboard/command-center-navigation-map.md`](../dashboard/command-center-navigation-map.md) |

### Schemas

- [`docs/contracts/living-architecture-map.schema.json`](../contracts/living-architecture-map.schema.json)
- [`schemas/product-intelligence/product-intelligence-event.schema.json`](../../schemas/product-intelligence/product-intelligence-event.schema.json)
- [`docs/operations/operational-health-dashboard.schema.json`](../operations/operational-health-dashboard.schema.json)
- [`docs/schema-registry.json`](../schema-registry.json)

### Dashboards

- [`docs/dashboard/operational-command-center.md`](../dashboard/operational-command-center.md)
- [`docs/dashboard/command-center-evidence-index.md`](../dashboard/command-center-evidence-index.md)
- [`docs/dashboard/command-center-navigation-map.md`](../dashboard/command-center-navigation-map.md)
- [`docs/ops-dashboard/index.html`](../ops-dashboard/index.html)
- [`docs/dashboard/operational-evidence-hub.html`](../dashboard/operational-evidence-hub.html)

### Runbooks relacionados

- [`docs/runbooks/operational-artifact-schema-validation.md`](operational-artifact-schema-validation.md)
- [`docs/runbooks/operational-artifact-discovery-index.md`](operational-artifact-discovery-index.md)
- [`docs/runbooks/delivery-evidence-index.md`](delivery-evidence-index.md)
- [`docs/runbooks/operational-governance-dashboard.md`](operational-governance-dashboard.md)
- [`docs/runbooks/ops-dashboard.md`](ops-dashboard.md)

### PRs recentes e evidências

| PR | Evidências versionadas |
|---|---|
| [PR145](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/145) | [`docs/evidence/pr145-clean-replacement-evidence.md`](../evidence/pr145-clean-replacement-evidence.md), [`docs/audit/pr145-clean-replacement-audit.md`](../audit/pr145-clean-replacement-audit.md) |
| [PR225](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/225) | [`docs/evidence/pr225-evidence-navigation-ui-sync.md`](../evidence/pr225-evidence-navigation-ui-sync.md), [`docs/product-intelligence/PR225_SUPERSEDED_BY_MAIN.md`](../product-intelligence/PR225_SUPERSEDED_BY_MAIN.md) |

### Evidências de CI

- [`docs/operations/ci-evidence-refresh-2026-06-25.md`](../operations/ci-evidence-refresh-2026-06-25.md)
- [`docs/POST_MERGE_CI_FIX_2026_06_23.md`](../POST_MERGE_CI_FIX_2026_06_23.md)

## Validação report-only

O workflow [`Living Architecture Traceability`](../../.github/workflows/living-architecture-traceability.yml) deve:

1. Carregar o JSON canônico.
2. Validar presença das seções principais.
3. Verificar se caminhos internos declarados existem no repositório.
4. Verificar se todo artifact declarado possui contrato versionado existente.
5. Publicar relatório em `audit/living-architecture/living-architecture-traceability-report.json`.
6. Não bloquear CI enquanto estiver em `report_only`; problemas devem ser registrados como pendências de governança.

## Critérios de manutenção

- Toda nova família de artifact operacional deve declarar `producer_workflow`, `contract` e pelo menos um consumidor ou runbook.
- Todo dashboard que consome JSON versionado deve apontar para schema ou contrato correspondente.
- Toda evidência de PR usada como referência recorrente deve ser versionada em `docs/evidence/`, `docs/audit/`, `docs/releases/` ou `docs/operations/`.
- Mudanças neste mapa não devem alterar runtime, deploy, secrets ou gates produtivos.
