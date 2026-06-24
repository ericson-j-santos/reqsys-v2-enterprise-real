from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Header

from .config import load_settings

app = FastAPI(title="ReqSys Ollama Local Gateway", version="0.1.0")


@app.get("/health")
def health(x_correlation_id: str | None = Header(default=None)) -> dict[str, object]:
    settings = load_settings()
    correlation_id = x_correlation_id or str(uuid4())
    return {
        "status": "ok",
        "service": "reqsys-ollama-local-gateway",
        "env": settings.env,
        "auth_required": settings.auth_required,
        "correlation_id": correlation_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
