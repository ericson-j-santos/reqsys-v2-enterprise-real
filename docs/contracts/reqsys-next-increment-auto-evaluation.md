# ReqSys Next Increment Auto Evaluation

## Objetivo

Avaliar automaticamente, de forma `report-only`, a sequência governada:

1. validar PRs abertas, Merge Queue e workflows obrigatórios;
2. consolidar os artefatos instrumentados de readiness e histórico;
3. publicar resumo executivo apenas com métricas instrumentadas;
4. calcular e expor ETA somente quando o histórico tiver evidência suficiente.

## Frequência

- execução horária;
- acionamento manual;
- execução após alteração do próprio contrato na `main`.

## Saídas

- `report.json`: contrato estruturado e auditável;
- `report.md`: resumo executivo para o GitHub Step Summary;
- artifact `reqsys-next-increment-auto-evaluation`, retido por 90 dias.

## Estados

- `READY_FOR_HUMAN_DECISION`: gates e evidências suficientes; decisão humana continua obrigatória;
- `ACTION_REQUIRED`: existe falha, pendência, evidência incompleta ou histórico insuficiente.

## Priorização automática

1. `remediate_failed_required_workflows`;
2. `complete_required_workflows`;
3. `complete_instrumented_evidence`;
4. `accumulate_instrumented_history`;
5. `governed_merge_of_eligible_prs`;
6. `validate_runtime_deploy_and_smoke`.

## Guardrails

- não realiza merge;
- não habilita auto-merge;
- não promove ambiente;
- não altera branch protection;
- não substitui required checks;
- aprovação humana permanece obrigatória;
- dados ausentes não são estimados.
