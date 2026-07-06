# Changelog — Issue #715 — Runtime Core / Event Bus

## Tipo

Incremento enterprise incremental e não invasivo.

## Contexto

O ReqSys já possui workflow governado, coordenador multiagente, GovBI telemetry/health e design tokens. O gap P0 identificado foi a ausência de um núcleo operacional reutilizável para eventos, retry, rastreabilidade e dead letter queue.

## Alterações

- Adicionado `backend/app/services/runtime_core.py`.
- Adicionado `RuntimeEventEnvelope` para padronizar eventos de agentes, workflows e integrações.
- Adicionado `RuntimeEventBus` síncrono/in-memory como fundação inicial.
- Adicionada `RetryPolicy` governada.
- Adicionada `DeadLetterItem` para falhas definitivas.
- Adicionados testes unitários em `backend/tests/test_runtime_core.py`.

## Decisão arquitetural

A primeira versão do Runtime Core é propositalmente in-memory e sem dependência externa. Isso reduz risco, preserva contratos existentes e permite evolução futura para SQL outbox, Redis, RabbitMQ, Kafka ou fila corporativa sem alterar o contrato base do envelope.

## Critérios atendidos

- [x] Incremento não invasivo.
- [x] Contratos existentes preservados.
- [x] Testes automatizados adicionados.
- [x] `correlation_id` padronizado no envelope.
- [x] Suporte a retry e dead letter queue.
- [x] Base preparada para integração futura com agentes/workflows.

## Próximo incremento recomendado

Integrar o Runtime Core ao workflow de requisitos de forma controlada:

- publicar evento `REQUISITO_TRANSICIONADO` após transição governada;
- registrar timeline técnica por `correlation_id`;
- expor endpoint de inspeção operacional do runtime;
- manter fallback seguro quando não houver handler externo.
