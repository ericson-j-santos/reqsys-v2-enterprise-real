from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.core.secrets import get_secret
from app.core.service_tokens import require_admin_or_service_token
from app.schemas.todo_global import TodoGlobalUpsertRequest, TodoGlobalUpsertResponse
from app.services.todo_global_notion import (
    NotionTodoGlobalClient,
    NotionTodoGlobalError,
)

router = APIRouter(prefix='/api/internal/todo-global', tags=['TODO Global'])
require_upsert_auth = require_admin_or_service_token('todo_global:upsert')


def _notion_config() -> tuple[str, str]:
    token = (get_secret('NOTION_TODO_GLOBAL_TOKEN', prefer_vault=True) or '').strip()
    data_source_id = (get_secret('NOTION_TODO_GLOBAL_DATA_SOURCE_ID', prefer_vault=True) or '').strip()
    if not token or not data_source_id:
        raise HTTPException(status_code=503, detail='TODO Global Notion não configurado')
    return token, data_source_id


@router.post('/upsert', response_model=TodoGlobalUpsertResponse)
async def upsert_todo_global(
    payload: TodoGlobalUpsertRequest,
    _ctx=Depends(require_upsert_auth),
) -> TodoGlobalUpsertResponse:
    token, data_source_id = _notion_config()
    async with httpx.AsyncClient(base_url='https://api.notion.com', timeout=20.0) as client:
        notion = NotionTodoGlobalClient(client, token, data_source_id)
        try:
            return await notion.upsert(payload)
        except NotionTodoGlobalError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from None
