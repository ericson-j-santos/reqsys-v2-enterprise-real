from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.operational_worker_heartbeat import OperationalWorkerHeartbeatSettings


def evaluate_heartbeat(
    path: Path,
    *,
    stale_after_seconds: float,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError('heartbeat ausente')

    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'heartbeat inválido: {exc}') from exc

    if payload.get('status') != 'running':
        raise RuntimeError(f"worker não está running: {payload.get('status')}")
    if payload.get('consumer_running') is not True:
        raise RuntimeError('consumer parado')
    if payload.get('recovery_running') is not True:
        raise RuntimeError('recovery worker parado')

    try:
        observed_at = datetime.fromisoformat(str(payload['timestamp']))
    except (KeyError, ValueError) as exc:
        raise RuntimeError('timestamp do heartbeat inválido') from exc
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    current = now or datetime.now(UTC)
    age_seconds = (current - observed_at.astimezone(UTC)).total_seconds()
    if age_seconds < 0:
        raise RuntimeError('heartbeat está no futuro')
    if age_seconds > stale_after_seconds:
        raise RuntimeError(f'heartbeat expirado: {age_seconds:.1f}s')

    return {
        'status': 'healthy',
        'age_seconds': round(age_seconds, 3),
        'heartbeat': payload,
    }


def main() -> None:
    settings = OperationalWorkerHeartbeatSettings.from_environment()
    result = evaluate_heartbeat(
        settings.path,
        stale_after_seconds=settings.stale_after_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
