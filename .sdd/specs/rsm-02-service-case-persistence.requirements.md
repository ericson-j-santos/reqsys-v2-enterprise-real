# RSM-02 — ServiceCase Persistence/API — Requisitos

Issue: #1784
E2E parcial: #1788

## Requisito 1 — persistência canônica
O ReqSys deve persistir ServiceCase e CaseEvent sem criar catálogo paralelo. service_id referencia gestao_ti_servicos.servico_id.

## Requisito 2 — idempotência persistente
idempotency_key deve possuir unicidade no banco. Repetição da mesma identidade lógica deve retornar o mesmo case_id sem segundo caso nem segundo efeito de criação.

## Requisito 3 — histórico append-only
Criação e transições válidas devem adicionar CaseEvent com event_id único, correlation_id e estados anterior/novo quando aplicável.

## Requisito 4 — concorrência
Transições devem exigir expected_version e atualizar somente quando a versão persistida coincidir. Escrita concorrente/stale deve falhar com conflito e sem sobrescrita silenciosa.

## Requisito 5 — transições fail-closed
A API deve reutilizar a máquina de estados do domínio RSM-01. Transição inválida não pode alterar o estado nem persistir CaseEvent.

## Requisito 6 — resolução com evidência
Transição para RESOLVED exige evidence_uri e evidence_sha256 válidos, persistidos no CaseEvent correspondente.

## Requisito 7 — E2E real sem mock
O harness deve iniciar a API real contra PostgreSQL real, chamar a API por HTTP e realizar leitura independente diretamente no PostgreSQL.

## Critérios de aceite (Acceptance Criteria)
1. POST /v1/service-cases persiste REQUEST válido e retorna case_id.
2. Replay com a mesma idempotency_key converge para o mesmo case_id e mantém COUNT(*)=1.
3. NEW -> TRIAGE -> IN_PROGRESS -> RESOLVED -> CLOSED é persistido.
4. CLOSED -> IN_PROGRESS retorna conflito e a leitura SQL independente continua CLOSED.
5. expected_version stale retorna conflito sem sobrescrita.
6. RESOLVED sem evidência é rejeitado sem mudança persistida.
7. Chave de idempotência inválida retorna 422 e não persiste caso.
8. O E2E registra ambiente, SHA, correlation_id, idempotency_key, entrada, esperado, observado e leitura independente.
9. O E2E usa PostgreSQL e HTTP reais; mocks/stubs não contam como integração.
10. Teams real permanece bloqueio externo explícito e não é apresentado como validado.
11. Pre-PR Readiness deve retornar READY_FOR_PR=passed no HEAD exato antes da abertura de PR.
