# Operational Artifact Schema Validation

## Objetivo

Validar automaticamente os contratos dos artifacts operacionais do ReqSys para reduzir risco de quebra silenciosa entre workflows, artifacts, dashboard e analytics.

## Contratos validados

| Artifact | Schema |
|---|---|
| `ci-lead-time-analytics.json` | `docs/contracts/ci-lead-time-analytics.schema.json` |
| `operational-history-snapshot.json` | `docs/contracts/operational-history-snapshot.schema.json` |
| `runtime-predictive-analytics.json` | `docs/contracts/runtime-predictive-analytics.schema.json` |

## Modo operacional

- Validação report-only de contrato e amostras sintéticas.
- Sem secrets.
- Sem deploy/runtime.
- Sem relaxamento de gates obrigatórios.
- Sem dependência externa de pacote Python.

## Métricas alvo

| Indicador | Meta |
|---|---:|
| Schemas carregáveis como JSON | 100% |
| Required keys cobertas por amostra | 100% |
| Tipos mínimos validados | 100% |
| Artifact de validação publicado | 100% |

## Limites

A validação inicial não substitui validação completa JSON Schema draft 2020-12. Ela garante contrato mínimo e integridade operacional sem dependências externas.

## Próxima evolução

Adicionar validação completa com biblioteca dedicada ou validador interno expandido quando houver série histórica suficiente e artifacts reais versionados.
