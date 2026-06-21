# Runbook — Operational Intelligence Platform

## Sintoma: relatório não enviado

1. Consultar `delivery_audit`.
2. Consultar `execution_logs`.
3. Validar `correlation_id`.
4. Reexecutar diagnóstico runtime.
5. Se houver tentativas esgotadas, consultar `dead_letter_queue`.
6. Reprocessar somente com aprovação se status estiver `DEGRADADO` ou `BLOQUEADO`.

## Sintoma: CI verde mas dashboard degradado

1. Validar evento em `operational_events`.
2. Verificar métricas em `runtime_metrics`.
3. Conferir health endpoint.
4. Bloquear promoção se não houver evidência operacional.

## Sintoma: excesso de tentativas

1. Abrir incidente.
2. Bloquear automação.
3. Validar dependência externa.
4. Registrar causa raiz.
5. Reativar somente após teste controlado.
