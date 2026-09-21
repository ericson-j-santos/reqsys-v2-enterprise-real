# Required Checks Stale Inventory

- Contrato: `reqsys-required-checks-stale-inventory` (schema `1.0.0`)
- Observado em: `2026-09-21T20:14:04.607852+00:00`
- Branch alvo: `main`
- Gap canônico: `OPS-GAP-GITOPS-CHECKS-001`
- Fonte dos contextos exigidos: `versioned_baseline`
- Decisão: `stale_or_misnamed_required_checks_detected`
- Bloqueante: `false`
- Workflows analisados: `563`
- Contextos produzíveis (check run names): `655`

## Classificação dos contextos exigidos

| Contexto exigido | Status | Produtores | Sugestão | Decisão registrada |
|---|---|---|---|---|
| `Branch Protection Audit` | `workflow_name_mismatch` | - | `Auditar proteção enterprise da branch` | rename → Auditar proteção enterprise da branch |
| `CI Enterprise Fast` | `workflow_name_mismatch` | - | `Backend fast checks`, `Frontend fast checks`, `Guardrails deterministicos`, `Sumario CI Enterprise Fast` | rename → Sumario CI Enterprise Fast |
| `CI — ReqSys v2 Enterprise` | `workflow_name_mismatch` | - | `CI Router (paths + Pareto)`, `CI Router Result`, `Frontend Responsive E2E (Playwright)`, `Pipeline Governança + Evidence Snapshot` | rename → CI Router Result |
| `Governance Quality Gates` | `workflow_name_mismatch` | - | `governance-validation` | rename → governance-validation |
| `Governança Padrão Ouro` | `workflow_name_mismatch` | - | `Validar artefatos de governança` | rename → Validar artefatos de governança |
| `Governed Merge Queue` | `workflow_name_mismatch` | - | `Estabilidade dos workflows no SHA atual`, `Gate de merge governado`, `Integração temporária contra base real do PR`, `Resolver contexto do PR`, `SDD — contrato da mudança no SHA do PR`, `Validação isolada do PR` | rename → Gate de merge governado |

## Validação da lista recomendada

| Contexto recomendado | Status | Produtores |
|---|---|---|
| `Auditar proteção enterprise da branch` | `active` | `Branch Protection Audit :: audit` |
| `CI Router Result` | `active` | `CI — ReqSys v2 Enterprise :: ci-result` |
| `Gate de merge governado` | `active` | `Governed Merge Queue :: merge-queue-gate` |
| `Required Fast Gate` | `active` | `ReqSys Required Fast Gate :: required-fast-gate` |
| `Security Baseline` | `active` | `Security Baseline Gate :: security-baseline` |
| `Sumario CI Enterprise Fast` | `active` | `CI Enterprise Fast :: ci-fast-summary` |
| `Validar artefatos de governança` | `active` | `Governança Padrão Ouro :: validar-governanca` |
| `governance-validation` | `active` | `Governance Quality Gates :: governance-validation` |

## Pendências

- Stale ou renomeados: `Branch Protection Audit`, `CI Enterprise Fast`, `CI — ReqSys v2 Enterprise`, `Governance Quality Gates`, `Governança Padrão Ouro`, `Governed Merge Queue`
- Sem decisão registrada: nenhuma

## Restrições

- Alteração automática de branch protection: `não permitida`.
- Remoção automática de contexto: `não permitida`.
- Produção tocada: `não`.
