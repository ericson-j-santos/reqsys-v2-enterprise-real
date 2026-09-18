# Codex Worker Pool — execução distribuída governada

## Objetivo

Consolidar as issues #1767, #1768, #1769, #1770 e #1771 num único contrato operacional reutilizável.

O serviço é o **control plane local/DEV de coordenação do pool**. Ele não substitui a fila canônica de autonomia operacional já existente em `backend/app/core/operational_queue.py`; para STG/PROD, o transporte durável continua sendo `OperationalQueue` com Redis Streams. O SQLite deste serviço guarda apenas estado de coordenação/lease do pool no escopo PC24x7 local/DEV.

Fluxo:

```text
issue/request
  -> enqueue idempotente
  -> Builder claim + lease
  -> worktree/branch exclusivos
  -> execução
  -> produced_sha
  -> Validator claim
  -> validação independente do SHA
  -> completed | retry | quarantine | blocked
```

## Invariantes

1. A identidade lógica é `SHA-256(repository|issue_number|request_id)`.
2. Replay da mesma identidade retorna a task existente.
3. `BEGIN IMMEDIATE` serializa a aquisição de task no SQLite; a atualização exige estado elegível e lease livre.
4. Um worker possui no máximo uma task ativa.
5. Um workspace ativo não pode ser compartilhado.
6. Worker `ESTUDO`, stale, sem Gateway, sem `state_validated` ou com `rules_sha` diferente do SHA canônico esperado não adquire trabalho.
7. Lease expirado é recuperado; ao atingir `max_attempts`, a task vai para `failed` + quarentena.
8. Builder entrega exatamente um `produced_sha`; Validator diferente valida o SHA.
9. Task `blocked` não mantém lease e não ocupa worker.
10. Token da API é lido de arquivo e não aparece em snapshot/log.
11. Toda task é vinculada a `base_sha` explícito; request sem SHA base falha antes de entrar na fila.

## Mapeamento de issues

| Issue | Cobertura |
|---|---|
| #1767 | workers, heartbeat, host/profile, claim exclusivo e recuperação |
| #1768 | `workspace_key`, branch determinística, uma task ativa por worker |
| #1769 | fila persistente, idempotência, lease, retry e quarentena |
| #1770 | papéis Builder/Validator e handoff por SHA |
| #1771 | `/v1/snapshot`, estado online/offline, ocupação e `why_idle` |

#1766 continua como pré-requisito operacional do ciclo completo. Seu bloqueio atual de token broker/permissão não deve ser mascarado por esta fila.

## Bloqueios externos

Quando uma dependência como DSN, segredo, permissão administrativa ou identidade externa estiver ausente:

1. worker marca a task como `blocked` com causa sanitizada;
2. lease é liberado imediatamente;
3. worker volta a buscar outra task;
4. após resolver a dependência, o operador/orquestrador executa `requeue`;
5. replay preserva a mesma `idempotency_key`.

## E2E mínimo

### Positivo
- registrar Builder e Validator prontos;
- enfileirar;
- Builder adquirir/iniciar;
- entregar `produced_sha`;
- Validator adquirir/concluir;
- `GET /v1/tasks/{task_id}` independente confirma `completed`.

### Negativo
- worker `ESTUDO` deve receber `409`;
- lease inválido não altera estado;
- segunda aquisição concorrente não recebe a mesma task.

### Replay
- repetir `POST /v1/tasks` com mesma combinação `repository/issue_number/request_id`;
- resposta deve ser `created=false` e manter o mesmo `task_id`.

### Falha
- expirar lease;
- recuperar a task;
- atingir o limite de tentativas;
- confirmar registro na quarentena.

## Limite de evidência atual

Os testes determinísticos podem provar o contrato em processo único/SQLite e HTTP. A prova física Desktop + Noteri só conta quando ambos passarem `dual_host_preflight` no mesmo SHA das regras e o Noteri estiver online. Nenhum teste simulado deve ser registrado como prova física de dois hosts.
