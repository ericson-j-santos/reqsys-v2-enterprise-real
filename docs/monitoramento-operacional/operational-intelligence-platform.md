# Operational Intelligence Platform — ReqSys

## Objetivo

Reduzir gaps operacionais críticos por meio de cinco capacidades integradas:

1. Telemetria distribuída.
2. Runtime intelligence.
3. Observabilidade viva.
4. Resiliência real.
5. Operação autônoma assistida.

## Rotas backend

- `GET /monitoramento-operacional/runtime/health`
- `POST /monitoramento-operacional/runtime/diagnostico`

## Tabelas

- `operational_events`
- `runtime_metrics`
- `dead_letter_queue`

## Critérios de aceite

- Toda resposta retorna `correlation_id`.
- Diagnóstico calcula score entre 0 e 100.
- Estado operacional é classificado como `SAUDAVEL`, `ATENCAO`, `DEGRADADO` ou `BLOQUEADO`.
- Ação autônoma assistida é sugerida.
- Estados degradado/bloqueado exigem aprovação humana.
- Falhas com tentativas esgotadas devem ser encaminhadas para fila de exceção operacional.
