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

## Validação report-only de contratos de artifacts

O workflow `Artifact Contract Validation` complementa esta validação sem alterar os workflows produtores. Ele inventaria artifacts JSON referenciados em `.github/workflows/` e em `docs/`, aplica o contrato mínimo de governança e publica os relatórios:

- `artifact-contract-validation-report.json`
- `artifact-contract-validation-report.md`

O índice canônico fica em `docs/contracts/artifact-contracts-index.md`. Nesta primeira versão, divergências de campos e contratos são apenas reportadas para orientar maturação progressiva; o CI não deve ser reprovado por essas divergências.
