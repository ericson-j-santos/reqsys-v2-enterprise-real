"""Métricas operacionais por feature — contadores in-process para observabilidade enterprise."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

_FEATURE_PREFIXES: tuple[tuple[str, str], ...] = (
    ('/api/requisitos', 'requisitos'),
    ('/requisitos', 'requisitos'),
    ('/api/pipeline', 'pipeline'),
    ('/pipeline', 'pipeline'),
    ('/govbi', 'govbi'),
    ('/api/ia', 'ia'),
    ('/ia/', 'ia'),
    ('/qualidade-ia', 'ia'),
    ('/rag', 'rag'),
    ('/codex', 'codex'),
    ('/wiki', 'wiki'),
    ('/auth', 'auth'),
    ('/api/runtime', 'runtime'),
    ('/monitoramento-operacional', 'runtime'),
    ('/operacao-autonoma', 'runtime'),
    ('/dashboard', 'dashboard'),
    ('/estatisticas', 'estatisticas'),
    ('/processos', 'processos'),
    ('/auditoria', 'auditoria'),
    ('/agents', 'agents'),
    ('/hub-lowcode', 'integracoes'),
    ('/webhooks', 'integracoes'),
    ('/figma-github', 'integracoes'),
    ('/v1/agile-runtime', 'agile'),
)


def identificar_feature(path: str) -> str:
    for prefix, feature in _FEATURE_PREFIXES:
        if path.startswith(prefix):
            return feature
    return 'core'


@dataclass
class FeatureMetricSnapshot:
    feature: str
    requests_total: int = 0
    errors_total: int = 0
    duration_ms_total: int = 0

    @property
    def avg_duration_ms(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return round(self.duration_ms_total / self.requests_total, 2)

    @property
    def error_rate(self) -> float:
        if self.requests_total == 0:
            return 0.0
        return round((self.errors_total / self.requests_total) * 100, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            'feature': self.feature,
            'requests_total': self.requests_total,
            'errors_total': self.errors_total,
            'duration_ms_total': self.duration_ms_total,
            'avg_duration_ms': self.avg_duration_ms,
            'error_rate': self.error_rate,
        }


@dataclass
class FeatureMetricsRegistry:
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _requests: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _duration_ms: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record(self, feature: str, status_code: int, duration_ms: int) -> None:
        with self._lock:
            self._requests[feature] += 1
            self._duration_ms[feature] += max(0, duration_ms)
            if status_code >= 400:
                self._errors[feature] += 1

    def snapshot(self) -> list[FeatureMetricSnapshot]:
        with self._lock:
            features = sorted(set(self._requests) | set(self._errors) | set(self._duration_ms))
            return [
                FeatureMetricSnapshot(
                    feature=feature,
                    requests_total=self._requests.get(feature, 0),
                    errors_total=self._errors.get(feature, 0),
                    duration_ms_total=self._duration_ms.get(feature, 0),
                )
                for feature in features
            ]

    def operational_analytics(self) -> dict[str, Any]:
        items = self.snapshot()
        total_requests = sum(item.requests_total for item in items)
        total_errors = sum(item.errors_total for item in items)
        return {
            'schema_version': '1.0.0',
            'features_tracked': len(items),
            'requests_total': total_requests,
            'errors_total': total_errors,
            'error_rate': round((total_errors / total_requests) * 100, 2) if total_requests else 0.0,
            'features': [item.to_dict() for item in items],
        }


REGISTRY = FeatureMetricsRegistry()
