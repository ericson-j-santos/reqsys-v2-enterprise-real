# Runbook — Operational Intelligence Platform

## Diagnóstico de runtime

1. Consultar `/monitoramento-operacional/runtime/health`.
2. Preservar o `correlation_id` da execução.
3. Enviar sinais controlados para `/monitoramento-operacional/runtime/diagnostico`.
4. Registrar score, riscos, recomendações e ação sugerida.
5. Se o estado for `DEGRADADO` ou `BLOQUEADO`, não promover ambiente nem executar ação destrutiva sem os gates aplicáveis.

## Falha operacional

1. Confirmar evidência no SHA/runtime atuais.
2. Verificar `/api/runtime/health`, readiness, métricas e dashboard.
3. Identificar causa raiz antes de rerun.
4. Usar a remediação governada atual; não criar retry paralelo para contornar falha.
5. Registrar correlação entre incidente, execução e evidência.

## CI verde, runtime degradado

CI verde é necessário, mas não suficiente. Validar os sinais de runtime e evidência pública antes de promoção.

## Escalada

- Falha transitória comprovada: revalidar de forma idempotente.
- Falha recorrente: abrir causa raiz e prevenção.
- Estado bloqueado: interromper avanço automático.
- Evidência ausente ou obsoleta: permanecer fail-closed.
