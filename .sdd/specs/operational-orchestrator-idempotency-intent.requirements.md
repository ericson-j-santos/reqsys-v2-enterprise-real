# Operational Orchestrator — idempotência por intenção completa

## Objetivo
Impedir que uma chave idempotente derivada de material reduzido masque uma ação operacional diferente.

## Requisitos
1. Replay idempotente só converge quando a intenção completa persistida coincide.
2. A intenção completa inclui source, project, environment, action_type, repository, branch, sha, risk, executor, next_action, validation e payload.
3. action_id, correlation_id, status, attempts e timestamps não participam da intenção funcional.
4. Mesma chave com intenção divergente falha fechado e preserva integralmente a ação original.
5. O endpoint de ingestão de workflow run retorna HTTP 409 para conflito de identidade.
6. O ciclo operacional também deve mapear conflito de identidade para HTTP 409.
7. O E2E dedicado deve provar replay equivalente, controle divergente e leitura SQLite independente após o conflito.
8. Nenhum segredo, deploy ou ambiente de produção é necessário para esta validação.

## Critérios de aceite
- replay equivalente retorna created=false e o mesmo action_id;
- run com mesmo material idempotente e payload divergente é rejeitado;
- SQLite contém exatamente uma ação para a chave;
- payload original permanece inalterado após o conflito;
- testes de núcleo e API verdes;
- Operational Orchestrator CI verde no HEAD exato;
- gates obrigatórios verdes antes do merge.
