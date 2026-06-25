#!/usr/bin/env python3
"""In-memory schema runtime metrics for ReqSys.

This module is intentionally dependency-free. Production integrations can adapt
`SchemaRuntimeMetrics.snapshot()` to Prometheus, OpenTelemetry, logs or BI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaRuntimeMetrics:
    counters: dict[str, int] = field(default_factory=dict)

    def inc(self, name: str, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.counters[name] = self.counters.get(name, 0) + amount

    def snapshot(self) -> dict[str, Any]:
        total = self.counters.get("schema_validation_total", 0)
        failed = self.counters.get("schema_validation_failed_total", 0)
        passed = self.counters.get("schema_validation_passed_total", 0)
        return {
            "schema_validation_total": total,
            "schema_validation_passed_total": passed,
            "schema_validation_failed_total": failed,
            "schema_version_mismatch_total": self.counters.get("schema_version_mismatch_total", 0),
            "schema_runtime_blocked_payload_total": self.counters.get("schema_runtime_blocked_payload_total", 0),
            "contract_runtime_coverage": 100 if total > 0 and failed == 0 else 0 if total == 0 else round((passed / total) * 100),
        }


DEFAULT_SCHEMA_RUNTIME_METRICS = SchemaRuntimeMetrics()
