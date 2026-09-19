# RSM-04 — SLA, atribuição, aprovação e histórico auditável — Requisitos

Issue: #1786
Parent: #1782
Depende de: RSM-01 (#1783), RSM-02 (#1784)
E2E parcial: #1788
Desbloqueia: RSM-05 (#1787), RSM-06 (#1788), RSM-07 (#1789)

## Requisito 1 — SLA determinístico
Uma `SlaPolicy` aplicada a um caso deve produzir prazos absolutos como função total de
(política, prioridade do caso, `created_at` do caso). Mesma entrada produz sempre o mesmo
prazo. O fator por prioridade é inteiro (`P1=1`, `P2=2`, `P3=4`, `P4=8`), sem ponto flutuante.
Política inativa não produz prazo.

## Requisito 2 — SLA não depende do relógio de leitura
Os prazos persistidos na aplicação da política são a autoridade e nunca são recalculados na
leitura. A avaliação do estado de SLA recebe o instante por parâmetro explícito; instante de
avaliação anterior ao início do caso, marco anterior ao início e datetime sem timezone são
rejeitados, de modo que manipulação de relógio não produza estado favorável silencioso.

## Requisito 3 — marcos derivados do histórico
Primeira resposta e resolução são derivadas do histórico append-only de eventos
(`rsm_service_case_events`), não gravadas em paralelo. Não existem duas versões da mesma verdade.

## Requisito 4 — atribuição auditável
Toda mudança de grupo/responsável grava linha nova em histórico append-only, com o estado
anterior explícito e `sequence` monotônica por caso. Nenhuma linha de histórico é atualizada.
Reatribuição idêntica é no-op e não gera registro extra. Grupo é obrigatório; responsável é opcional.

## Requisito 5 — aprovação opcional e rejeição auditável
Aprovação é solicitada explicitamente e decidida uma única vez. A decisão é terminal: aprovação
já decidida não pode ser alterada. A rejeição preserva aprovador, motivo e instante no histórico.

## Requisito 6 — transições fail-closed sob portão de aprovação
`PENDING_APPROVAL -> IN_PROGRESS` exige ao menos uma aprovação `APPROVED` no caso. Ausência de
aprovação, aprovação apenas `PENDING` ou apenas `REJECTED` bloqueiam a transição sem alterar
estado nem versão. O portão entra por registro de guarda, sem que o módulo de casos precise
conhecer o módulo de operações.

## Requisito 7 — concorrência e idempotência
Toda operação exige `event_id`. O mesmo `event_id` só é aceito para o mesmo efeito e o mesmo
caso; reaproveitado para outro efeito, é rejeitado com conflito. Replay converge para o mesmo
resultado sem segundo efeito e sem segundo evento no histórico.

## Requisito 8 — leitura independente
Estado, SLA, atribuição corrente, histórico de atribuições, aprovações e histórico de eventos
devem ser comprováveis por leitura SQL direta, sem passar pela API que os escreveu.

## Requisito 9 — E2E real sem mock
O harness deve iniciar a API real contra PostgreSQL real, chamar a API por HTTP e realizar
leitura independente diretamente no PostgreSQL. Mock/stub não conta como integração física.
O E2E recalcula o prazo esperado por fora do código sob teste.

## Critérios de aceite (Acceptance Criteria)
1. `POST /v1/sla-policies` registra política e é idempotente por `code`.
2. Política com `resolution_minutes < response_minutes` retorna 422.
3. `POST /v1/service-cases/{case_id}/sla` grava prazos iguais aos recalculados de forma
   independente a partir de `started_at`, dos minutos da política e do fator da prioridade.
4. Replay do mesmo `event_id` de SLA retorna `duplicate=true` e mantém um único `SLA_APPLIED`.
5. Política inexistente retorna 404; segunda política divergente no mesmo caso retorna 409.
6. Leitura com `evaluated_at` anterior ao início do caso retorna 422.
7. Leitura com `evaluated_at` após o prazo de resolução retorna `RESOLUTION_BREACHED`.
8. Atribuição grava estado anterior, `sequence` cresce e o histórico não é reescrito.
9. Reatribuição idêntica é no-op; grupo vazio retorna 422; caso inexistente retorna 404.
10. `event_id` reaproveitado para outro efeito retorna 409.
11. `PENDING_APPROVAL -> IN_PROGRESS` retorna 409 sem aprovação, com aprovação apenas `PENDING`
    e após `REJECTED`, sem alterar estado nem versão.
12. Decisão terminal reaberta retorna 422; replay da decisão retorna `duplicate=true`.
13. Aprovação `APPROVED` libera a transição mesmo havendo rejeição anterior no histórico.
14. Leitura SQL independente confirma estado, SLA, histórico de atribuições ordenado, aprovações
    ordenadas com motivo da rejeição e contagem de eventos por tipo.
15. O E2E registra ambiente, SHA exato, `correlation_id`, entrada, esperado, observado, leitura
    independente, replay e controles negativos.
16. Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.
