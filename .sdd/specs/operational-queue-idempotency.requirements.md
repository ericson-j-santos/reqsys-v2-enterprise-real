# Operational Queue — Idempotência por intenção — Requisitos

## Objetivo
Impedir que uma `idempotency_key` reutilizada masque uma tarefa operacional diferente nos providers `memory` e `redis_streams`.

## Requisitos
1. A intenção protegida pela chave é `task_type + payload + max_attempts`.
2. `correlation_id` e `task_id` são metadados de tentativa/transporte e não alteram a identidade funcional.
3. Replay equivalente retorna a tarefa original sem segundo enqueue.
4. Reuso da mesma chave com tipo, payload ou `max_attempts` divergente deve falhar fechado com conflito.
5. O provider em memória e o Redis Streams devem aplicar a mesma regra.
6. A API `POST /api/operational-autonomy/tasks` deve mapear conflito de identidade para HTTP 409.
7. Após conflito, leitura independente do provider deve confirmar uma única tarefa e preservação integral da intenção original.
8. CI deve executar os testes backend no HEAD exato antes do merge.

## Critérios de aceite
- replay equivalente converge para o mesmo `task_id`;
- payload divergente é rejeitado;
- `task_type` divergente é rejeitado;
- `max_attempts` divergente é rejeitado;
- memória mantém `total_tasks=1`;
- Redis Streams mantém `total_tasks=1` e a tarefa original;
- API retorna 409 no controle divergente;
- gates obrigatórios verdes no SHA atual.
