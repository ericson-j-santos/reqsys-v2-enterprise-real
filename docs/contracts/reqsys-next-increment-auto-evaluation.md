# ReqSys Next Increment Auto Evaluation

## Objetivo

Avaliar automaticamente, de forma `report-only`, a sequência governada:

1. validar PRs abertas, Merge Queue e workflows obrigatórios;
2. consolidar artefatos instrumentados de readiness e histórico;
3. executar smoke público nos endpoints contratuais do runtime;
4. calcular throughput de integração e lead time de merge;
5. publicar resumo executivo apenas com métricas instrumentadas;
6. calcular e expor ETA somente quando o histórico tiver evidência suficiente.

## Frequência

- execução horária;
- acionamento manual;
- execução após alteração do contrato na `main`.

## Fontes instrumentadas

- GitHub Pull Requests abertas e mergeadas;
- GitHub Actions e required workflows;
- artifacts `instrumented-executive-readiness` e `instrumented-executive-history`;
- runtime público `https://reqsys-api.fly.dev`:
  - `/health`;
  - `/api/runtime/health`;
  - `/api/runtime/readiness`;
  - `/api/runtime/liveness`.

## Saídas

- `report.json`: contrato estruturado e auditável, schema `1.1.0`;
- `report.md`: resumo executivo para o GitHub Step Summary;
- artifact `reqsys-next-increment-auto-evaluation`, retido por 90 dias.

## Indicadores

- estabilidade dos required workflows;
- sucesso e latência média dos smoke checks públicos;
- PRs mergeadas em 24 horas e 7 dias;
- lead time mediano entre criação e merge;
- throughput paralelo das PRs abertas mergeáveis;
- maturidade histórica, tendência e confiança instrumentada;
- ETA proveniente do histórico, sem preenchimento manual.

## Estados

- `READY_FOR_HUMAN_DECISION`: gates, runtime e evidências suficientes; decisão humana continua obrigatória;
- `ACTION_REQUIRED`: existe falha, pendência, runtime indisponível, evidência incompleta ou histórico insuficiente.

## Priorização automática

1. `remediate_failed_required_workflows`;
2. `complete_required_workflows`;
3. `restore_runtime_and_smoke_evidence`;
4. `complete_instrumented_evidence`;
5. `accumulate_instrumented_history`;
6. `governed_merge_of_eligible_prs`;
7. `maintain_runtime_and_delivery_baseline`.

## Guardrails

- não realiza merge;
- não habilita auto-merge;
- não promove ambiente;
- não altera branch protection;
- não substitui required checks;
- aprovação humana permanece obrigatória;
- dados ausentes não são estimados.
