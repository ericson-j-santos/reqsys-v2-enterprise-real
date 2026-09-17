# Central Global — plano de controle operacional

Núcleo determinístico da Central de Solicitações de IA. Resolve três gargalos
transversais: roteamento de executor, limite de trabalho simultâneo e prova de
conclusão.

## Ciclo canônico

```
solicitação → causa raiz → executor → execução → validação → evidência
```

A Solicitação de Trabalho (`WorkRequest`) é a unidade única de estado. O
executor nunca é escolhido pelo produtor: a Central classifica.

## Componentes

| Componente | Módulo | Responsabilidade |
| --- | --- | --- |
| Executor Router | `runtime/app/domain/central/executor_router.py` | Classifica a solicitação em um executor por regra nomeada e auditável |
| WIP por causa raiz | `runtime/app/domain/central/wip_policy.py` | Limita causas raiz ativas (default 3), não solicitações |
| Evidence Ledger | `runtime/app/domain/central/evidence_ledger.py` | Registro canônico de "comprovadamente concluído", vinculado ao SHA |
| Serviço | `runtime/app/application/services/central_service.py` | Fecha o ciclo e impõe as transições válidas |
| Store | `runtime/app/infrastructure/repositories/central_store.py` | Persistência do estado: memória (DEV) ou Redis (durável) |
| API | `runtime/app/api/central.py` | Endpoints sob `/api/central` |

## Regras que o código impõe

1. **Bloqueio de identidade vence roteamento técnico.** Falta de consentimento,
   credencial ou permissão roteia para `human_gate` mesmo que a solicitação
   pareça de CI ou Graph — executar apenas antecipa a falha de autenticação
   para dentro do E2E.
2. **Solicitação sem regra correspondente vai para `human_gate`**, nunca para um
   executor por aproximação.
3. **WIP é contado por causa raiz.** Vinte sintomas de três defeitos ocupam três
   vagas, não vinte. Causa já em andamento mantém a vaga; `wip_breach` sinaliza
   violação em vez de abandonar trabalho iniciado.
4. **`EVIDENCED` exige as quatro verificações em PASS**: caso positivo, controle
   negativo, idempotência e leitura por fonte independente.
5. **Qualquer verificação em FAIL leva a `BLOCKED`.** Parcialidade não é
   arredondada para sucesso.
6. **Evidência é vinculada ao SHA.** Registrar evidência em um SHA novo
   invalida (`SUPERSEDED`) o registro anterior, e a conclusão é recusada com
   HTTP 409 se a evidência corrente não for do SHA da solicitação.

## Persistência e concorrência

O estado vive em um `CentralStore`, escolhido por `STORAGE_BACKEND`:

| Backend | Implementação | Uso |
| --- | --- | --- |
| `memory` | `InMemoryCentralStore` | DEV e testes; **perde tudo no reinício** |
| `redis` | `RedisCentralStore` | Operação real; sobrevive a reinício e é compartilhado entre réplicas |

Chaves em Redis, sob `CENTRAL_REDIS_PREFIX` (default `reqsys:runtime:central`):

```
:request:<id>              JSON da solicitação
:requests                  SET com os ids, para listagem
:evidence:<id>             JSON do registro corrente de evidência
:evidence:<id>:history     LIST append-only com o histórico
```

Garantias de concorrência, para que duas réplicas não percam escrita uma da outra:

* **criação** é atômica por `SET NX` — um replay do produtor devolve a mesma
  solicitação em vez de criar uma segunda;
* **toda atualização** passa por compare-and-swap otimista (`WATCH`/`MULTI`),
  com até 5 tentativas antes de `ConcurrentUpdateError`. Duas réplicas tentando
  a mesma transição: uma vence, as demais recebem `InvalidTransitionError`;
* **o histórico de evidência é append-only** — a invalidação por mudança de SHA
  entra como novo evento, não sobrescreve o anterior;
* **a admissão de WIP é idempotente** e recalculada do estado persistido, logo
  converge igual em qualquer réplica.

Um `asyncio.Lock` de processo não daria nenhuma dessas garantias entre réplicas
e por isso não é o mecanismo primário — ele só protege o backend em memória.

Ordem de escrita em `registrar_evidencia`: a evidência é gravada antes de
alinhar a solicitação, porque é a fonte da verdade da conclusão. Se o processo
cair entre as duas, o status da solicitação fica atrasado, mas `transicionar`
continua consultando o ledger e nenhuma conclusão indevida passa.

### Variáveis de ambiente

| Variável | Default | Efeito |
| --- | --- | --- |
| `STORAGE_BACKEND` | `memory` | `redis` ativa a persistência durável da Central |
| `REDIS_URL` | `redis://localhost:6379/0` | Conexão (compartilhada com o controle de paralelismo) |
| `CENTRAL_REDIS_PREFIX` | `reqsys:runtime:central` | Prefixo das chaves |
| `CENTRAL_MAX_ACTIVE_ROOT_CAUSES` | `3` | Limite de causas raiz ativas simultâneas |

## Endpoints

| Método | Rota | Uso |
| --- | --- | --- |
| POST | `/api/central/work-requests` | Registra e classifica (idempotente por correlation_id + projeto + título) |
| GET | `/api/central/work-requests[/{id}]` | Estado corrente |
| POST | `/api/central/work-requests/{id}/transition` | Transição de ciclo; `409` em transição inválida ou conclusão sem evidência |
| GET | `/api/central/admission-plan` | Plano de WIP: causas admitidas e enfileiradas |
| GET | `/api/central/next[?executor=]` | Próximo item executável; `204` quando não há |
| POST | `/api/central/evidence` | Registra verificações no ledger |
| GET | `/api/central/evidence/{id}` | Leitura independente do ledger |

## Validação E2E

### Funcional

```bash
cd runtime
QUEUE_BACKEND=memory STORAGE_BACKEND=memory \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 &
python scripts/e2e_central.py     # exige instância limpa; código 1 em falha
```

O script cobre caso positivo, três controles negativos (conclusão sem evidência
completa, conclusão após mudança de SHA, `human_gate` fora da fila executável),
idempotência de registro e leitura por endpoint independente.

### Durabilidade

Exige backend Redis e um reinício real do runtime entre as duas fases:

```bash
cd runtime
QUEUE_BACKEND=redis STORAGE_BACKEND=redis REDIS_URL=redis://localhost:6379/0 \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 &
python scripts/e2e_central_durability.py seed     # cria, conclui e grava o id
# reinicie o runtime aqui
python scripts/e2e_central_durability.py verify   # confirma fila, estado e evidência
```

Controle contra falso positivo: a mesma sequência com `STORAGE_BACKEND=memory`
**precisa** reprovar (`404` na fase `verify`). Se passar nos dois backends, o
teste não está provando durabilidade.

### Integração Redis

`tests/test_central_store_redis_integration.py` roda contra um Redis real
(inclusive registro e transição concorrentes) quando
`REQSYS_RUNTIME_REDIS_INTEGRATION=1`, no mesmo padrão da integração de
`todo-events`.

## Estado e limites conhecidos

* Os executores ainda não executam: a Central decide e enfileira o trabalho. O
  acoplamento de cada executor real é incremento subsequente.
* O preflight de identidade (verificação ativa de consentimento, segredo e
  validade antes da fila) não está implementado; hoje o bloqueio é declarado
  pela regra `identity.blocked` a partir dos sinais da solicitação.
