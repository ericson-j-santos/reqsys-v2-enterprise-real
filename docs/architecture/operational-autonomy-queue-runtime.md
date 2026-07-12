# Runtime de Autonomia Operacional por Fila

## Decisão

Implementar uma primeira fundação de autonomia operacional no ReqSys usando fila assíncrona, worker controlado, contrato de tarefa e pontos de observabilidade.

Este incremento usa fila em memória por padrão para reduzir risco de implantação e evitar dependências externas obrigatórias. O contrato foi desenhado para permitir evolução posterior para Redis Streams, RabbitMQ, Azure Service Bus ou orquestrador como Temporal sem alterar os consumidores HTTP.

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
| Contrato de fila | `backend/app/core/operational_queue.py` | Modelar tarefa, status, idempotência, retry e DLQ lógica |
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
- `max_attempts` limita retries.
- DLQ lógica evita loop infinito.
- Payloads devem evitar PII desnecessária.
- Integrações externas devem entrar por adaptadores específicos, não diretamente no worker base.

## Próximo incremento recomendado

Substituir o backend em memória por adapter persistente, preferencialmente Redis Streams para ambiente inicial ou RabbitMQ/Azure Service Bus para ambiente corporativo, mantendo a mesma interface pública da API.
