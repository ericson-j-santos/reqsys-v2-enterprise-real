# OPS-GAP-OBSERVABILITY-001 — contexto distribuído de logs

## Objetivo

Avançar o gap canônico de observabilidade distribuída sem abrir nova frente e sem custo adicional, padronizando contexto causal entre runtime, workflows e evidências.

## Requisitos

1. O log JSON deve preservar `correlation_id`, `causation_id` e `workflow_run_id` quando disponíveis.
2. `X-Causation-Id` e `X-Workflow-Run-Id` só podem ser propagados quando passarem por validação allowlist e limite de tamanho.
3. Valores com whitespace arbitrário, quebra de linha ou mais de 128 caracteres devem falhar fechado e não aparecer nos headers de resposta.
4. O filtro de redaction para tokens e dados pessoais deve continuar ativo.
5. O caso positivo deve provar propagação dos três identificadores.
6. O controle negativo deve provar ausência de propagação para identificadores inválidos.
7. O TODO Padrão Ouro deve distinguir itens já evidenciados de dependências ainda abertas de retenção, backend OTLP, alertas e runtime real.
8. O incremento deve permanecer `gap_fix`, sem deploy ou promoção de ambiente.

## Validação

- `services/environment-observability-api/tests/test_api.py`
- `services/environment-observability-api/tests/test_log_security.py`
- `services/environment-observability-api/tests/test_collector_contract.py`
- Pre-PR Readiness no HEAD exato e `behind_by=0`.

## E2E

A validação local/CI comprova contrato e controles contra falso positivo. A conclusão operacional de retenção/alertas/backend OTLP continua separada e não deve ser inferida destes testes.
