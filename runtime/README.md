# ReqSys Runtime — Jobs assíncronos

Runtime executável para processamento assíncrono governado do ReqSys.

## Objetivo

Receber chamadas via API, persistir e enfileirar trabalho antes de confirmar aceite, consultar status e processar jobs de forma desacoplada. O Runtime suporta adapter em memória para testes/DEV e Redis para fila e armazenamento duráveis.

## Endpoints

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/health` | Health check básico |
| `GET` | `/api/runtime/health` | Readiness do runtime e fila |
| `GET` | `/api/runtime/analytics` | Métricas de jobs, fila, DLQ e lease |
| `POST` | `/api/jobs` | Criar job assíncrono genérico |
| `GET` | `/api/jobs/{job_id}` | Consultar status do job |
| `POST` | `/api/todo-events` | Aceitar `TodoEvent v1` para sincronização assíncrona do TODO Global |
| `GET` | `/api/todo-events/{event_id}` | Consultar o processamento de um evento de TODO |

## Semântica de aceite

`202 Accepted` significa apenas que o evento foi validado, persistido e aceito pela fila. Não significa que o TODO Global já foi atualizado. O efeito final deve ser confirmado pela consulta de status e, no E2E, por leitura independente da fonte canônica.

O mesmo `event_id` gera o mesmo job lógico e não é reenfileirado. Eventos diferentes que representam o mesmo TODO preservam a mesma `idempotency_key`; o adapter do TODO Global deve fazer upsert por essa chave para convergir em um único TODO lógico.

## Fila e confiabilidade

Com `QUEUE_BACKEND=redis` e `STORAGE_BACKEND=redis`, o Runtime usa Redis para persistência e transporte duráveis. O fluxo inclui:

- lease distribuído e renovação periódica;
- recuperação de jobs órfãos após expiração de lease;
- retry com backoff exponencial limitado;
- fila atrasada para retries sem loop imediato;
- DLQ/quarentena após o limite de tentativas;
- backpressure explícito com `503` e `Retry-After` quando a capacidade é atingida;
- `correlation_id` ponta a ponta;
- sanitização de erros antes da persistência operacional.

## TODO Global

O contrato `TodoEvent v1` segue a regra global de TODOs operacionais. Estados terminais são fail-closed:

- `BLOQUEADO` exige causa e próxima ação;
- `CONCLUÍDO` exige critério de conclusão e evidência;
- ausência de `TODO_GLOBAL_ADAPTER_URL` nunca é tratada como sucesso: o job entra em retry e, se persistir, em DLQ.

O adapter externo deve receber o evento completo e executar upsert idempotente na fonte canônica. Até existir E2E real contra o adapter autorizado do TODO Global, a integração externa deve permanecer `PENDENTE` ou `PARCIAL`.

## Configuração principal

```text
ENABLE_ASYNC_WORKER=true
QUEUE_BACKEND=redis
STORAGE_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
MAX_QUEUE_SIZE=1000
ASYNC_JOB_MAX_TENTATIVAS=3
RETRY_BACKOFF_BASE_SECONDS=1
RETRY_BACKOFF_MAX_SECONDS=60
TODO_GLOBAL_ADAPTER_URL=https://adapter-autorizado.example/todo-global/upsert
```

Não versionar credenciais ou tokens na URL/configuração.

## Execução local

```bash
cd runtime
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

No Windows PowerShell:

```powershell
cd runtime
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## OpenAPI canônico

O contrato canônico gerado pelo FastAPI permanece versionado em:

```text
docs-site/assets/openapi/reqsys-runtime-openapi-v0.7.0.json
```

Para gerar novamente:

```bash
cd runtime
python scripts/export_openapi.py
```

Para validar drift:

```bash
cd runtime
python scripts/export_openapi.py --check
```

O workflow `Runtime Async Jobs` executa testes e essa validação.

## Testes

```bash
cd runtime
pip install -r requirements.txt
pytest
```

Os testes devem cobrir aceite, replay do mesmo `event_id`, convergência por `idempotency_key`, controles fail-closed, retry/DLQ, backpressure, lease/recuperação e contrato OpenAPI.

## Próximos incrementos

- Materializar o adapter autorizado do TODO Global e provar leitura independente E2E.
- Executar teste de falha/recovery com Redis real em ambiente de integração.
- Transformar WIP/WSJF e Dashboard em consumidores independentes do TODO Global.
- Manter a reconciliação periódica apenas como rede de segurança para drift/perda externa.
