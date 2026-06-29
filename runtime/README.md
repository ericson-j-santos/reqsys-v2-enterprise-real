# ReqSys Runtime — Jobs assíncronos

Runtime executável inicial para o workflow assíncrono do ReqSys.

## Objetivo

Receber chamadas via API, criar jobs, enfileirar processamento, consultar status e permitir worker local com `httpx.AsyncClient` para chamadas externas.

## Endpoints

| Método | Endpoint | Finalidade |
|---|---|---|
| `GET` | `/health` | Health check básico |
| `GET` | `/api/runtime/health` | Readiness do runtime e fila |
| `GET` | `/api/runtime/analytics` | Métricas de jobs e fila |
| `POST` | `/api/jobs` | Criar job assíncrono |
| `GET` | `/api/jobs/{job_id}` | Consultar status do job |

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

## Worker local

Por padrão, o worker local fica desativado para testes e previsibilidade em DEV.

```bash
ENABLE_ASYNC_WORKER=true uvicorn app.main:app --reload
```

## Exemplo de POST

```http
POST /api/jobs
Content-Type: application/json
```

```json
{
  "origem": "power_automate",
  "tipo_operacao": "enviar_resposta",
  "destino": "reqsys_runtime",
  "payload": {
    "requisito_id": "REQ-001",
    "status": "aprovado"
  },
  "metadata": {
    "versao_contrato": "0.5.0",
    "correlation_id": "power-automate-0001"
  }
}
```

Resposta esperada:

```http
HTTP/1.1 202 Accepted
Location: /api/jobs/JOB-YYYYMMDDHHMMSS-XXXXXXXX
```

```json
{
  "job_id": "JOB-20260628000000-ABC12345",
  "status": "queued",
  "correlation_id": "power-automate-0001",
  "status_url": "/api/jobs/JOB-20260628000000-ABC12345",
  "message": "Processamento recebido e enfileirado."
}
```

## Testes

```bash
cd runtime
pip install -r requirements.txt
pytest
```

## Decisões técnicas

- `asyncio.Queue` como adapter DEV inicial.
- Repositório em memória para primeira fatia executável.
- Worker local controlado por `ENABLE_ASYNC_WORKER`.
- `httpx.AsyncClient` isolado em gateway outbound.
- `correlation_id` propagado por header `X-Correlation-Id`.
- Estados compatíveis com contrato OpenAPI `v0.4.0`.

## Próximo incremento recomendado

- Adicionar adapter Redis ou Azure Service Bus.
- Persistir jobs em banco relacional.
- Expor logs estruturados JSON com `correlation_id`.
- Adicionar backoff real com atraso progressivo entre retentativas.
- Sincronizar OpenAPI gerado automaticamente com `docs-site/assets/openapi`.
