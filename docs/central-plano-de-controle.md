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
| Worker | `runtime/app/application/services/central_worker.py` | Puxa o próximo item, executa e registra evidência |
| Métricas | `runtime/app/domain/central/metrics.py` | Lead Time to Evidence e onde o tempo é gasto |
| Executor HTTP | `runtime/app/infrastructure/executors/http_executor.py` | Executor genérico: produz o efeito e comprova o que conseguiu |
| Executor GitHub | `runtime/app/infrastructure/executors/github_executor.py` | Executor nativo: dispara um workflow e comprova a execução |
| Registro de executores | `runtime/app/infrastructure/executors/registry.py` | De `ExecutorKind` para o adaptador configurado |
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

## Execução

O worker fecha o ciclo:

```
next → EXECUTING → executor → evidência → EVIDENCED
```

Invariantes que o worker preserva:

1. **Nunca conclui sem evidência completa.** Registra o que o executor
   comprovou e tenta a conclusão; faltando verificação, a solicitação fica em
   `AWAITING_EVIDENCE` e o ciclo reporta quais faltam. A recusa é dupla: além
   da guarda do worker, `transicionar` consulta o ledger.
2. **Nenhuma falha vira silêncio.** Executor não configurado, solicitação sem
   SHA, endpoint indisponível, exceção não tratada ou verificação reprovada
   viram `BLOCKED` com `blocker` e `next_action`.
3. **`human_gate` nunca é executado.** Não aceita adaptador e não entra na fila
   executável — automatizá-lo anularia o próprio gate.
4. **Corrida entre réplicas cede a vez.** Se outra réplica assumiu o item, a
   transição é recusada e o ciclo devolve `CEDIDO`, com a evidência já gravada
   preservada para quem assumiu.

### Contrato do executor HTTP

`POST {url}` com a solicitação e `idempotency_key` (derivada de
`request_id + sha`, logo estável entre replays); resposta:

```json
{"accepted": true,
 "effect_id": "<id do efeito>",
 "duplicate_effect": false,
 "verification_url": "<URL de leitura independente>",
 "evidence_run_url": "<opcional>"}
```

O adaptador então comprova, nesta ordem:

| Verificação | Como é comprovada | Reprova quando |
| --- | --- | --- |
| `positive` | POST aceito com `effect_id` | resposta sem `accepted`/`effect_id` |
| `idempotency` | repete o POST com a mesma chave | o replay cria um segundo efeito |
| `independent_read` | `GET verification_url` | o efeito lido diverge do produzido |
| `negative_control` | envia o `negative_probe` configurado | o executor **aceita** carga inválida |

Verificação que o endpoint não suporta **não vira PASS**: fica `PENDING`, a
evidência permanece `PARTIAL` e a solicitação não é concluída. É por isso que um
executor não consegue, sozinho, declarar trabalho comprovado.

### Executor nativo de GitHub Actions

Efeito produzido: um `workflow_dispatch` no repositório e SHA da solicitação,
carregando `request_id`, `correlation_id` e `idempotency_key` como inputs — de
modo que a execução resultante seja rastreável até a Solicitação de Trabalho.

| Verificação | Como é comprovada |
| --- | --- |
| `positive` | dispatch aceito (204) e execução presente para o SHA |
| `idempotency` | antes de disparar, procura execução existente para (workflow, SHA, `workflow_dispatch`); se existe, **não dispara** |
| `independent_read` | relê a execução pelo id e confere o `head_sha` |
| `negative_control` | dispara para `negative_probe_ref` inexistente e exige recusa 4xx |

A idempotência no GitHub não pode ser verificada disparando duas vezes — isso
criaria um segundo efeito real. O adaptador verifica o **mecanismo**: após o
dispatch, reexecuta a decisão de guarda e confirma que um replay resolveria para
a execução existente.

Sem token, o adaptador **bloqueia** com `github_token_ausente` e a próxima ação
("provisionar `CENTRAL_GITHUB_TOKEN` com escopo `actions:write`") em vez de
tentar e falhar na autenticação dentro do E2E — o gargalo de identidade aparece
onde custa barato. Também bloqueia sem SHA, sem repositório ou com repositório
fora do formato `owner/repo`.

### Configuração dos executores

`CENTRAL_EXECUTOR_ENDPOINTS` é um objeto JSON; `human_gate` é recusado:

```json
{"ci_repair": "https://executor/ci",
 "graph": {"url": "https://executor/graph", "negative_probe": {"sha": "invalido"}},
 "github": {"kind": "github",
            "workflow": "ci-repair.yml",
            "repository": "owner/repo",
            "negative_probe_ref": "refs/heads/inexistente"}}
```

Sem `kind`, o executor é HTTP genérico; com `kind: "github"`, é o nativo.

`POST /api/central/worker/cycle` executa um único ciclo (operação assistida e
E2E) e responde `403` em produção, onde o ciclo é do worker contínuo.

## Métricas

A métrica principal não é commit nem PR verde: é **Lead Time to Evidence** — o
tempo entre a solicitação entrar e existir evidência completa no SHA corrente.
As demais séries existem para explicar onde esse tempo é gasto.

| Série | O que responde |
| --- | --- |
| `lead_time_to_evidence` | p50, p95 e máximo, em segundos, com o nº de amostras |
| `por_status` / `por_executor` | onde o trabalho está e quem deveria executá-lo |
| `evidencia_por_status` | quanto está `PARTIAL`, `BLOCKED` ou `EVIDENCED` |
| `wip` | causas raiz ativas, enfileiradas e se o limite foi violado |
| `bloqueios.por_causa` | bloqueios agrupados pelo prefixo do `blocker` — a causa, não a instância |
| `aguardando_evidencia.verificacoes_pendentes` | qual verificação mais impede a conclusão |
| `aguardando_evidencia.idade_maxima_segundos` | há quanto tempo o item mais antigo espera comprovação |

Duas decisões de medição que evitam número bonito e falso:

* o lead time é medido do `created_at` da solicitação até o `recorded_at` do
  registro de evidência que a tornou `EVIDENCED` — não até o `updated_at`, que
  qualquer escrita posterior moveria;
* evidência de **outro SHA não entra na amostra**: mediria um lead time
  fictício, de uma versão que não é a concluída.

Disponível em `GET /api/central/metrics` e embutida em `GET /api/runtime/analytics`
sob a chave `central`.

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
| `CENTRAL_EXECUTOR_ENDPOINTS` | `""` | Mapa JSON de executor para endpoint |
| `CENTRAL_EXECUTOR_SERVICE_TOKEN` | `""` | Token enviado aos executores HTTP (`X-Service-Token`) |
| `CENTRAL_GITHUB_TOKEN` | `""` | Token do executor nativo GitHub (escopo `actions:write`) |
| `CENTRAL_WORKER_ENABLED` | `false` | Liga o worker contínuo no runtime |
| `CENTRAL_WORKER_IDLE_SECONDS` | `5` | Espera do worker quando a fila está vazia |

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
| GET | `/api/central/metrics` | Séries operacionais, incluindo Lead Time to Evidence |
| POST | `/api/central/worker/cycle[?executor=]` | Executa um ciclo; `403` em produção |

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

### Ciclo executável

Sobe um executor HTTP real e comprova o ciclo de ponta a ponta:

```bash
cd runtime
CENTRAL_EXECUTOR_ENDPOINTS='{"ci_repair": {"url": "http://127.0.0.1:8098/executar",
                                           "negative_probe": {"sha": "invalido"}},
                             "graph": "http://127.0.0.1:8098/executar"}' \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 &
python scripts/e2e_central_executor.py   # sobe o executor na 8098
```

Cobre o caso positivo (até `EVIDENCED`, com leitura do efeito no próprio
executor) e três controles negativos: executor sem controle negativo não
conclui, executor não configurado bloqueia com causa, e `human_gate` não é
executado. O script também sobe uma API do GitHub simulada e roda o **executor
nativo** por HTTP real, além de conferir as métricas sobre os dados que os
ciclos produziram.

O E2E do executor nativo exercita o adaptador contra uma API simulada: prova o
tratamento do protocolo de ponta a ponta, **não** o comportamento contra
`api.github.com`, que exige token provisionado.

### Integração Redis

`tests/test_central_store_redis_integration.py` roda contra um Redis real
(inclusive registro e transição concorrentes) quando
`REQSYS_RUNTIME_REDIS_INTEGRATION=1`, no mesmo padrão da integração de
`todo-events`.

## Estado e limites conhecidos

* O preflight de identidade (verificação ativa de consentimento, segredo e
  validade antes da fila) não está implementado; hoje o bloqueio é declarado
  pela regra `identity.blocked` a partir dos sinais da solicitação.
