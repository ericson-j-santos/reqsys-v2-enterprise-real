from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    task_type: Literal['code', 'chat', 'rag'] = 'code'
    prompt: str = Field(min_length=1, max_length=50000)
    contexto: str = Field(default='', max_length=12000)
    entrada: str = Field(default='', max_length=30000)
    correlation_id: str = Field(min_length=1, max_length=120)
    source: str = Field(default='reqsys-codex', max_length=80)


class ChatResponse(BaseModel):
    response: str
    model: str
    correlation_id: str
    provider: str = 'ollama'
    latency_ms: int = 0
