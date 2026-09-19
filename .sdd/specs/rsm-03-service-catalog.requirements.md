# RSM-03 — Catálogo mínimo e abertura de solicitação — Requisitos

Issue: #1785
Parent: #1782
Depende de: RSM-01 (#1783), RSM-02 (#1784)
E2E parcial: #1788

## Requisito 1 — catálogo mínimo sem plataforma paralela
O ReqSys deve permitir registrar `ServiceOffering` vinculada a um `Service` já existente em
`gestao_ti_servicos`. Não deve ser criado catálogo corporativo paralelo, portal genérico de
formulários nem motor genérico de workflow.

## Requisito 2 — esquema declarativo de campos
Cada oferta deve declarar seu esquema de entrada de forma declarativa e versionada
(`STRING`, `INTEGER`, `BOOLEAN`, `ENUM`), com obrigatoriedade, limites e opções explícitos.
Esquema inválido deve ser rejeitado no registro da oferta.

## Requisito 3 — validação fail-closed da entrada
A abertura de solicitação deve aceitar somente campos declarados na oferta. Campo não
declarado, campo obrigatório ausente ou nulo, valor fora das opções, string acima do limite,
inteiro fora dos limites e tipo divergente devem ser rejeitados sem coerção implícita
(`bool` não é aceito como inteiro).

## Requisito 4 — oferta ativa é pré-condição
Oferta inexistente deve retornar 404. Oferta existente porém inativa, ou oferta de serviço
inativo, deve retornar conflito. Nenhum dos dois pode persistir `ServiceCase`.

## Requisito 5 — rastreabilidade e idempotência
A solicitação criada deve receber `correlation_id` do chamador e exigir `idempotency_key`
SHA-256. O registro da oferta deve ser idempotente por `code`.

## Requisito 6 — replay sem segundo caso
Repetição da mesma `idempotency_key` na mesma oferta deve convergir para o mesmo `case_id`,
sem segundo caso e sem segundo vínculo. `idempotency_key` já usada por outra oferta, ou por
caso fora do catálogo, deve ser rejeitada com conflito.

## Requisito 7 — vínculo catálogo -> caso legível de forma independente
O vínculo entre oferta e caso, com os campos submetidos normalizados, deve ser persistido e
comprovável por leitura SQL direta, sem passar pela API que o escreveu.

## Requisito 8 — E2E real sem mock
O harness deve iniciar a API real contra PostgreSQL real, chamar a API por HTTP e realizar
leitura independente diretamente no PostgreSQL. Mock/stub não conta como integração física.

## Critérios de aceite (Acceptance Criteria)
1. `POST /v1/service-offerings` registra oferta ativa com esquema declarativo válido.
2. Repetição do mesmo `code` retorna `duplicate=true` e mantém `COUNT(*)=1` da oferta.
3. Esquema de campo inválido (ex.: `ENUM` sem `options`) retorna 422.
4. `POST /v1/service-offerings/{offering_id}/requests` cria `ServiceCase(type=REQUEST)`
   vinculado à oferta e ao mesmo `service_id`.
5. Oferta inexistente retorna 404 e não persiste caso.
6. Oferta inativa retorna 409 e não persiste caso.
7. Campo obrigatório ausente, campo não declarado, valor fora do `ENUM`, string acima do
   `max_length` e inteiro com tipo divergente retornam 422 e não persistem caso.
8. Replay com a mesma `idempotency_key` converge para o mesmo `case_id`, com
   `COUNT(*)=1` de caso e de vínculo.
9. `idempotency_key` reaproveitada em outra oferta retorna 409 e não cria vínculo.
10. Leitura SQL independente confirma `catálogo -> caso`: `offering_id`, `code`,
    `case_type=REQUEST`, `correlation_id` e campos submetidos normalizados.
11. O E2E registra ambiente, SHA exato, `correlation_id`, `idempotency_key`, entrada,
    esperado, observado, leitura independente, replay e controles negativos.
12. O E2E usa PostgreSQL e HTTP reais; mocks/stubs não contam como integração.
13. Pre-PR Readiness deve retornar `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.
