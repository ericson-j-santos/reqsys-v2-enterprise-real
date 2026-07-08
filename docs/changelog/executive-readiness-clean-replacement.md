# Executive Readiness Clean Replacement

## Resumo

Substitui o PR conflitante por uma implementação limpa baseada na `main` atual, sem alterar o builder principal `build_runtime_executive_index.py`.

## Decisão técnica

Para evitar conflitos com merges paralelos, o Runtime Executive Index passa a ser enriquecido por pós-processador offline:

- `scripts/enrich_runtime_executive_readiness.py`

Esse script lê:

- `docs/ops-dashboard/data/runtime-executive-index.json`
- `artifacts/executive-readiness-gate/executive-readiness-gate.json`

E adiciona ao contrato público:

- `schema_version = 1.2.0`
- `summary.production_ready`
- `summary.executive_readiness_decision`
- `cards.executive_readiness`
- `links.executive_readiness_gate`
- guardrail de precedência do readiness gate

## Visual

O card Executive Readiness é injetado de forma idempotente em:

- `docs/ops-dashboard/index.html`
- `docs/ops-dashboard/runtime-executive.html`

## Guardrails

- Sem chamada GitHub/API em runtime público.
- Sem secrets.
- Sem deploy.
- Sem alteração de produção.
- Interface consome somente `runtime-executive-index.json`.
- Pós-processamento offline para reduzir conflito de merge.

## Substitui

Substitui funcionalmente o PR #752, que ficou impossível de fazer merge por divergência com a `main` após merges paralelos.
