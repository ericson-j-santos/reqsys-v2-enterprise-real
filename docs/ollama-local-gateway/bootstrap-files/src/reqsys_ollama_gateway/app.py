from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .audit import auditar
from .config import load_settings
from .ollama_client import OllamaClient
from .schemas import ChatRequest, ChatResponse

_settings = load_settings()
app = FastAPI(title='ReqSys Ollama Local Gateway', version='0.2.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_settings.allowed_origins),
    allow_credentials=True,
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
)


def _validar_api_key(x_api_key: str | None, auth_required: bool) -> None:
    if not auth_required:
        return
    settings = load_settings()
    if not settings.api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='API key nao configurada no gateway')
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='API key invalida')


@app.get('/health')
def health(x_correlation_id: str | None = Header(default=None)) -> dict[str, object]:
    settings = load_settings()
    correlation_id = x_correlation_id or str(uuid4())
    return {
        'status': 'ok',
        'service': 'reqsys-ollama-local-gateway',
        'version': '0.2.0',
        'env': settings.env,
        'auth_required': settings.auth_required,
        'correlation_id': correlation_id,
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
    }


@app.post('/v1/chat', response_model=ChatResponse)
def chat(
    body: ChatRequest,
    x_api_key: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None),
) -> ChatResponse:
    settings = load_settings()
    _validar_api_key(x_api_key, settings.auth_required)
    correlation_id = body.correlation_id or x_correlation_id or str(uuid4())

    auditar('chat_inicio', {
        'correlation_id': correlation_id,
        'model': body.model,
        'task_type': body.task_type,
        'source': body.source,
        'prompt': body.prompt,
    })

    inicio = time.perf_counter()
    try:
        client = OllamaClient(settings)
        resposta, latencia_ollama = client.generate(body.model, body.prompt)
    except Exception as exc:  # noqa: BLE001
        auditar('chat_erro', {'correlation_id': correlation_id, 'erro': str(exc)[:200]})
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail='Falha ao consultar Ollama') from exc

    latencia_ms = max(latencia_ollama, int((time.perf_counter() - inicio) * 1000))
    resultado = ChatResponse(
        response=resposta,
        model=body.model,
        correlation_id=correlation_id,
        latency_ms=latencia_ms,
    )
    auditar('chat_concluido', {
        'correlation_id': correlation_id,
        'model': body.model,
        'latency_ms': latencia_ms,
        'response': resposta,
    })
    return resultado
