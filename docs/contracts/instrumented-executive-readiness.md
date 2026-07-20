# Instrumented Executive Readiness

## Objetivo

Substituir avaliações executivas manuais por métricas calculadas automaticamente a partir dos contratos operacionais existentes do ReqSys.

## Fontes

- `reqsys-single-state-consumer-readiness/report.json` — adoção por Governança, Runtime e Analytics;
- `runtime-validation-snapshot.json` — runtime público, deploy/pós-merge, smoke, risco, confiança e produção;
- `merge-intelligence-index.json` — mergeabilidade, pressão da fila e lanes paralelas;
- `ci-lead-time-analytics.json` — taxa real de sucesso da CI e lead time.

## Indicadores instrumentados

- progresso técnico;
- progresso operacional;
- usuário final;
- governança;
- produção;
- confiança;
- risco operacional;
- estabilidade da CI;
- throughput de PRs paralelos;
- cobertura das métricas.

Cada indicador informa sua proveniência no campo `metric_provenance`. Dados ausentes são representados por `null` e reduzem `metric_coverage_percent`; não são substituídos por estimativas subjetivas.

## ETA

O contrato não inventa datas. Enquanto não existir histórico instrumentado suficiente para calcular velocidade de evolução, `eta_calendar` permanece `null` e `eta_reason` explicita a limitação.

## Guardrails

- `mode=report_only`;
- `production_blocker=false`;
- `automatic_promotion_allowed=false`;
- nenhuma alteração de deploy, merge ou produção;
- artifact auditável retido por 90 dias.
