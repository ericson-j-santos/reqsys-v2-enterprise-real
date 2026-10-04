from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PublishPlannerTaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    plan_id: str = Field(..., min_length=1, alias='planId')
    bucket_id: str = Field(..., min_length=1, alias='bucketId')
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default='', max_length=4000)
    due_date: str = Field(..., min_length=1, alias='dueDate')
    priority: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1, alias='sourceId')
    requester: str = Field(..., min_length=1)
    correlation_id: str | None = Field(default=None, alias='correlationId')


class PublishPlannerTaskResponse(BaseModel):
    ok: bool
    status: str
    idempotency_key: str
    attempt_id: int
    correlation_id: str
    planner_task_id: str | None = None
    erro: str | None = None
