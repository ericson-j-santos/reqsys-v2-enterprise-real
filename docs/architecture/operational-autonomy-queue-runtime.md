# Runtime de Autonomia Operacional por Fila

## Decisão

Implementar uma primeira fundação de autonomia operacional no ReqSys usando fila assíncrona, worker controlado, contrato de tarefa e pontos de observabilidade.

O provider é plugável. DEV e testes podem usar memória; homologação e produção exigem Redis Streams e falham de forma explícita quando a configuração ou a conectividade não estão disponíveis. Não há fallback silencioso para memória nesses ambientes.

## Objetivo

Transformar fluxos hoje potencialmente síncronos em tarefas operacionais rastreáveis, reprocessáveis e observáveis.

Exemplos de uso futuro:

- análise de requisito;
- geração de BDD;
- validação QA;
- automação GitHub;
- notificação Teams;
- envio de relatório por email;
- homologação DEV -> STG -> PROD.

## Componentes adicionados

| Componente | Arquivo | Responsabilidade |
| --- | --- | --- |
| Contrato e providers | `backend/app/core/operational_queue.py` | Modelar tarefa e fornecer providers `memory` e `redis_streams` |
| Worker | `backend/app/core/operational_worker.py` | Consumir tarefa e executar ação operacional controlada |
| API | `backend/app/api/operational_autonomy.py` | Enfileirar, consultar status, executar worker uma vez e expor saúde |
| Testes | `backend/tests/test_operational_queue.py` | Validar fila, idempotência, retry e DLQ |
| Testes | `backend/tests/test_operational_worker.py` | Validar processamento controlado pelo worker |

## Endpoints

### Enfileirar tarefa

```http
POST /api/operational-autonomy/tasks
X-Correlation-Id: reqsys-demo-001
Content-Type: application/json
```

```json
{
  "task_type": "generic",
  "payload": {
    "action": "validar-runtime"
  },
  "idempotency_key": "validar-runtime-001",
  "max_attempts": 3
}
```

### Executar worker uma vez

```http
POST /api/operational-autonomy/worker/run-once
```

### Consultar tarefa

```http
GET /api/operational-autonomy/tasks/{task_id}
```

### Saúde da fila

```http
GET /api/operational-autonomy/health
```

## Estados de tarefa

| Estado | Significado |
| --- | --- |
| `pending` | Tarefa aguardando processamento |
| `running` | Tarefa retirada da fila pelo worker |
| `completed` | Tarefa concluída com resultado |
| `failed` | Reservado para falha intermediária |
| `dead_letter` | Tentativas esgotadas; exige análise operacional |

## Governança

- Toda tarefa possui `correlation_id`.
- `idempotency_key` evita duplicidade lógica.
- retry usa backoff exponencial e `max_attempts` limita as tentativas.
- Redis persiste payload, timestamps, resultado e motivo da última falha.
- tentativas esgotadas são enviadas a uma Redis Stream de DLQ.
- Payloads devem evitar PII desnecessária.
- Integrações externas devem entrar por adaptadores específicos, não diretamente no worker base.

## Configuração

| Variável | DEV/testes | STG/PROD |
| --- | --- | --- |
| `OPERATIONAL_QUEUE_PROVIDER` | `memory` ou `redis_streams` | `redis_streams` |
| `OPERATIONAL_QUEUE_REDIS_URL` | opcional no modo memória | obrigatória |
| `OPERATIONAL_QUEUE_KEY_PREFIX` | `reqsys:operational` | prefixo isolado por ambiente |
| `OPERATIONAL_QUEUE_CONSUMER_GROUP` | `reqsys-operational-workers` | grupo dos workers |
| `OPERATIONAL_QUEUE_RETRY_BASE_SECONDS` | `1` | base do backoff exponencial |

O endpoint de saúde informa `provider`, `connected`, `durable`, `queued_items`,
`processing_items`, `dlq_items` e `oldest_message_age_seconds`.

## Próximo incremento recomendado

Executar o worker operacional como processo independente e adicionar recuperação de
mensagens pendentes abandonadas por consumer inativo, com lease/claim governado e métricas.
