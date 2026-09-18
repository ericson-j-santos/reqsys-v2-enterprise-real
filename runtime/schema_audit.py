#!/usr/bin/env python3
"""Audit event model for ReqSys schema runtime enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SchemaAuditEvent:
    correlation_id: str
    contract_name: str
    schema_version: str | None
    valid: bool
    errors: list[str] = field(default_factory=list)
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "occurred_at": self.occurred_at,
            "correlation_id": self.correlation_id,
            "contract_name": self.contract_name,
            "schema_version": self.schema_version,
            "valid": self.valid,
            "errors": self.errors,
        }


class SchemaRuntimeAuditSink:
    def __init__(self) -> None:
        self._events: list[SchemaAuditEvent] = []

    def append(self, event: SchemaAuditEvent) -> None:
        self._events.append(event)

    def snapshot(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]


DEFAULT_SCHEMA_RUNTIME_AUDIT = SchemaRuntimeAuditSink()
