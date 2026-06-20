# 2026-06-20 — REQSYS-OPER-005 — Gate de CI

## Regra

O incremento `/monitoramento-operacional` só pode sair de draft após:

- branch sincronizada com `main`;
- CI verde;
- testes backend executados;
- build frontend executado;
- E2E responsivo executado;
- evidência registrada no workflow.

## Estado atual

Implementação inicial criada em branch própria. Aguardando abertura de PR draft e execução de CI.

Refs #46
