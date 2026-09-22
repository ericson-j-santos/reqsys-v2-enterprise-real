# Instrumented Executive History

Contrato histórico do Estado Único ReqSys para persistir snapshots da prontidão executiva instrumentada e calcular ETA com velocidade observada.

## Fonte

- `reqsys-instrumented-executive-readiness`.
- Último artifact bem-sucedido do workflow `Instrumented Executive Readiness`.
- Último artifact histórico bem-sucedido, quando disponível.

## Saída

`artifacts/instrumented-executive-history/history.json`

Campos principais:

- `snapshot_count`: quantidade de snapshots preservados;
- `metric_coverage_percent`: cobertura da coleta mais recente;
- `points`: snapshots ordenados e limitados aos 180 mais recentes;
- `eta.mvp`, `eta.production`, `eta.gold_standard`;
- `velocity_percent_per_day`: velocidade observada, nunca estimada manualmente;
- `eta_days`: projeção somente quando existem dois ou mais pontos e velocidade positiva.

## Política de ETA

- marco atingido: `eta_days = 0`;
- menos de dois pontos: `insufficient_history`;
- fonte ausente: `insufficient_evidence`;
- velocidade nula ou negativa: `no_positive_velocity`;
- velocidade positiva: `projected`.

## Guardrails

- `report_only`;
- não faz merge, deploy ou promoção;
- não cria bloqueio de produção;
- não substitui aprovação humana;
- não inventa ETA quando o histórico é insuficiente.
