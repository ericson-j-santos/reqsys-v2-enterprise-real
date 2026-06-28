# Contract Artifacts Index v0.3.0

Este artifact consolida a rastreabilidade operacional entre contrato OpenAPI, coleção Postman, documentação Power Automate e validações CI.

## Arquivo canônico

```text
docs/ops-dashboard/data/contract-artifacts-index-v0.3.0.json
```

## Objetivo

Dar ao Ops Dashboard uma fonte única para exibir:

- contrato OpenAPI disponível;
- coleção Postman candidata;
- cobertura de paths críticos;
- gaps de validação automatizada;
- próximos incrementos de governança contratual.

## Guardrails

- Artifact only.
- Não altera runtime.
- Não altera backend.
- Não altera workflows.
- Não contém secrets.
- Não declara ambiente público como saudável sem evidência de smoke.

## Próximo incremento recomendado

Renderizar `contract-artifacts-index-v0.3.0.json` no Ops Dashboard / Strategic Governance com cards de semáforo para OpenAPI, Postman, CI e runtime sync.
