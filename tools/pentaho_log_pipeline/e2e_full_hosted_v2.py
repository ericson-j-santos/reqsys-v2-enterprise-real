from __future__ import annotations

import uuid
from dataclasses import replace

import e2e_full_hosted as base


def canonical_uuid(value: object) -> str:
    return str(uuid.UUID(str(value)))


_original_query_one = base.query_one


def query_one(sql: str, params: tuple[object, ...] = ()) -> tuple[object, ...] | None:
    row = _original_query_one(sql, params)
    if row is None:
        return None
    if "CONVERT(varchar(36), e.correlation_id)" in sql:
        values = list(row)
        values[-1] = canonical_uuid(values[-1])
        return tuple(values)
    return row


_original_reserve = base.SqlServerQueue.reserve


def reserve(self: base.SqlServerQueue, consumer: str, quantity: int, lease_seconds: int) -> list[base.LogItem]:
    items = _original_reserve(self, consumer, quantity, lease_seconds)
    return [
        replace(
            item,
            fila_id=canonical_uuid(item.fila_id),
            execucao_id=canonical_uuid(item.execucao_id),
            correlation_id=canonical_uuid(item.correlation_id),
        )
        for item in items
    ]


base.query_one = query_one
base.SqlServerQueue.reserve = reserve


if __name__ == "__main__":
    raise SystemExit(base.main())
