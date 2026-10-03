# OPS-GAP-OBSERVABILITY-001 — contexto distribuído de logs

## Objetivo

Avançar o gap canônico de observabilidade distribuída sem abrir nova frente e sem custo adicional, padronizando contexto causal entre runtime, workflows e evidências.

## Requisitos

1. O log JSON deve preservar `correlation_id`, `causation_id` e `workflow_run_id` quando disponíveis.
2. `X-Causation-Id` e `X-Workflow-Run-Id` só podem ser propagados quando passarem por validação allowlist e limite de tamanho.
3. Valores com whitespace arbitrário, quebra de linha ou mais de 128 caracteres devem falhar fechado e não aparecer nos headers de resposta.
4. O filtro de redaction para tokens e dados pessoais deve continuar ativo, sem classificar um `workflow_run_id` numérico validado como CPF.
5. O TODO Padrão Ouro deve distinguir itens já evidenciados de dependências ainda abertas de retenção, backend OTLP, alertas e runtime real.
6. O incremento deve permanecer `gap_fix`, sem deploy ou promoção de ambiente.

## Critérios de aceite

1. O caso positivo comprova propagação de `correlation_id`, `causation_id` e `workflow_run_id`.
2. O controle negativo comprova ausência de propagação de `causation_id` e `workflow_run_id` inválidos, inclusive sem fallback para `GITHUB_RUN_ID`.
3. O teste de segurança comprova que redaction existente permanece ativa, preserva `workflow_run_id` numérico validado e redige `workflow_run_id` inválido ou com tentativa de injeção.
4. O contrato HTTP em `/api/v1/environment` declara suporte aos novos identificadores.
5. Os testes mapeados no SDD passam no HEAD exato.
6. O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato e `behind_by=0` antes da abertura da PR.
7. Retenção, alertas, backend OTLP e operação real permanecem explicitamente fora da conclusão deste incremento.

## Validação

- `services/environment-observability-api/tests/test_api.py`
- `services/environment-observability-api/tests/test_log_security.py`
- `services/environment-observability-api/tests/test_collector_contract.py`
- Pre-PR Readiness no HEAD exato e `behind_by=0`.

## E2E

A validação local/CI comprova contrato, propagação positiva e controles negativos contra falso positivo. A conclusão operacional de retenção, alertas e backend OTLP continua separada e não deve ser inferida destes testes.
