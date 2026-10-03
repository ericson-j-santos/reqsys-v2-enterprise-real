# Workflow assíncrono com fila e httpx

> **Versão:** `0.4.0`  
> **Objetivo:** definir o padrão operacional para recebimento de eventos via API, enfileiramento, processamento assíncrono com worker e chamadas externas usando `httpx.AsyncClient`.

## Decisão arquitetural

O ReqSys deve responder rapidamente ao cliente com `202 Accepted`, persistir o job, enfileirar o processamento e delegar integrações externas para um worker assíncrono.

```mermaid
flowchart LR
    A[Cliente / Power Automate / Frontend] --> B[API ReqSys]
    B --> C[Validação DTO]
    C --> D[(Tabela de Jobs)]
    D --> E[Fila Redis / RabbitMQ / Azure Service Bus]
    E --> F[Worker Assíncrono]
    F --> G[httpx.AsyncClient]
    G --> H[API externa]
    F --> I[(Status, logs e resultado)]
    A --> J[GET /api/jobs/{job_id}]
    J --> I
```

## Endpoints canônicos

| Método | Endpoint | Finalidade | Resposta esperada |
|---|---|---|---|
| `POST` | `/api/jobs` | Criar job assíncrono | `202 Accepted` |
| `GET` | `/api/jobs/{job_id}` | Consultar status do job | `200 OK` |
| `GET` | `/api/runtime/analytics` | Expor métricas operacionais | `200 OK` |

## Payload de entrada

```json
{
  "origem": "power_automate",
  "tipo_operacao": "enviar_resposta",
  "destino": "reqsys_runtime",
  "payload": {
    "requisito_id": "REQ-001",
    "status": "aprovado",
    "comentario": "Validado pela área de negócio"
  },
  "metadata": {
    "versao_contrato": "0.4.0",
    "correlation_id": "power-automate-0001"
  }
}
```

## Resposta imediata

```http
HTTP/1.1 202 Accepted
Location: /api/jobs/JOB-20260628-0001
```

```json
{
  "job_id": "JOB-20260628-0001",
  "status": "queued",
  "correlation_id": "power-automate-0001",
  "status_url": "/api/jobs/JOB-20260628-0001",
  "message": "Processamento recebido e enfileirado."
}
```

## Estados do job

| Estado | Significado | Ação operacional |
|---|---|---|
| `queued` | Recebido e aguardando worker | Monitorar backlog |
| `processing` | Worker iniciou processamento | Acompanhar timeout |
| `completed` | Processamento concluído | Registrar evidência |
| `retrying` | Falha recuperável, aguardando nova tentativa | Validar destino externo |
| `failed` | Falha após tentativas configuradas | Abrir investigação |
| `dead_letter` | Mensagem isolada para análise manual | Aplicar remediação governada |

## Worker com httpx

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
)
async def enviar_payload_externo(url: str, payload: dict, correlation_id: str) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-Id": correlation_id,
    }

    timeout = httpx.Timeout(20.0, connect=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
```

## Estrutura recomendada de implementação

```text
app/
├── api/
│   └── routes_jobs.py
├── application/
│   └── use_cases/
│       ├── criar_job_assincrono.py
│       └── consultar_status_job.py
├── domain/
│   └── models/
│       └── job_assincrono.py
├── infrastructure/
│   ├── http/
│   │   └── httpx_gateway.py
│   ├── queue/
│   │   └── queue_gateway.py
│   └── repositories/
│       └── job_repository.py
└── workers/
    └── processar_jobs.py
```

## Regras de governança

- Todo job deve possuir `correlation_id`.
- O payload original deve ser persistido com trilha de auditoria e mascaramento de PII quando aplicável.
- Retentativas devem usar backoff exponencial e limite explícito de tentativas.
- Falhas não recuperáveis devem ir para `dead_letter`.
- O worker não deve executar ação produtiva sem contrato de destino, autenticação e timeout configurados.
- O endpoint síncrono não deve aguardar API externa para evitar timeout no Power Automate.

## Critérios de aceite

- `POST /api/jobs` documentado em OpenAPI.
- `GET /api/jobs/{job_id}` documentado em OpenAPI.
- Estados do job padronizados.
- Fluxo Mermaid navegável na documentação viva.
- Versão `0.4.0` registrada em `VERSION.json` e changelog.

## Próximo incremento recomendado

Implementar a primeira fatia executável em runtime:

1. DTOs Pydantic para `AsyncJobCreateRequest` e `AsyncJobStatusResponse`.
2. Repositório em memória para DEV.
3. Worker local assíncrono controlado por feature flag.
4. Testes unitários para transição de estados.
5. Adapter real com Redis/RabbitMQ/Azure Service Bus conforme ambiente.
