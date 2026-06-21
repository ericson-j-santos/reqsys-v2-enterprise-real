# ADR-022 — Operational Intelligence Platform

## Status
Proposto

## Contexto
O ReqSys precisa reduzir gaps críticos de telemetria distribuída, runtime intelligence, observabilidade viva, resiliência real e operação autônoma assistida.

## Decisão
Implementar uma plataforma operacional viva com:

- `correlation_id` obrigatório;
- healthcheck operacional;
- diagnóstico runtime;
- score operacional;
- retry/backoff;
- dead-letter queue;
- dashboards navegáveis;
- ações autônomas assistidas;
- bloqueio de falso positivo operacional.

## Gates
Produção deve bloquear:

- execução sem `correlation_id`;
- automação sem `execution_logs`;
- entrega crítica sem `delivery_audit`;
- retry sem limite;
- dashboard sem evidência;
- status avançado sem validação real.

## Consequências
A decisão aumenta rastreabilidade, reduz falhas silenciosas e cria base para IA operacional auditável.

## Referências
- ADR-021 — Operational Runtime Governance
- Evidence-Based Execution
- Automation Runtime Governance
- Living Architecture
