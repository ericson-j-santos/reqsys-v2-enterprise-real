# 715 — Runtime Requisitos Inspection

## Contexto

Após consolidar a publicação de eventos do Runtime Core na transição de requisitos, este incremento expõe uma rota de inspeção operacional para apoiar smoke checks, evidência contínua e diagnóstico governado.

## Entrega

- Nova rota GET `/api/requisitos/runtime/inspection`.
- Snapshot do Runtime Core de requisitos via `resumir_runtime_requisitos()`.
- Health mínimo com status, eventos publicados, dead letters e quantidade de handlers registrados.
- Contrato `reqsys-requisitos-runtime-inspection-v1`.
- Teste de contrato via `TestClient`.

## Risco

Baixo. Incremento aditivo, sem mudança de contrato existente, sem secrets e sem alteração destrutiva.

## Próximo incremento recomendado

Adicionar esta rota aos smoke/runtime checks automáticos pós-merge e ao snapshot executivo de evidências.
