# Runtime Executive Post-Merge Snapshot

## Contexto

Automatiza a publicação do snapshot executivo pós-merge contendo runtime, smoke, qualidade, segurança, merge intelligence, evidência e validação operacional.

## Entrega

- Estende o `Runtime Validation Consolidator` para reagir também ao workflow `Runtime Production Smoke Governed`.
- Baixa o artifact de smoke público governado quando disponível.
- Gera `docs/ops-dashboard/data/runtime-executive-index.json` junto com o `executive-brief.json`.
- Publica ambos no artifact consolidado `runtime-validation-evidence`.
- Inclui resumo executivo no `GITHUB_STEP_SUMMARY` com score e risco.

## Resultado esperado

Após cada execução relevante de runtime/smoke/pós-merge, o pipeline passa a produzir um snapshot executivo único consumível pelo dashboard operacional, sem intervenção manual.

## Próximo incremento recomendado

Expor o `runtime-executive-index.json` no dashboard HTML operacional como painel executivo único de produção.
