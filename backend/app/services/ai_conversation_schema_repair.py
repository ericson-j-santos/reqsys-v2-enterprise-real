from __future__ import annotations

import hashlib
import json

from sqlalchemy import Column, String, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn

_TABLE = 'ai_conversations'
_REQUIRED_COLUMNS: dict[str, int] = {
    'data_classification': 20,
    'classification_lock_sha256': 64,
    'requested_provider': 30,
    'authorized_provider': 30,
    'policy_mode': 20,
    'policy_decision': 20,
    'policy_reason': 500,
    'policy_correlation_id': 160,
    'tenant_id': 120,
    'area_id': 120,
    'requester_id': 160,
    'cost_center': 120,
}


def _quote(conn, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _add_missing_columns(conn) -> list[str]:
    inspector = inspect(conn)
    if _TABLE not in inspector.get_table_names():
        return []

    existing = {column['name'] for column in inspector.get_columns(_TABLE)}
    table = _quote(conn, _TABLE)
    added: list[str] = []
    for name, length in _REQUIRED_COLUMNS.items():
        if name in existing:
            continue
        column = Column(name, String(length=length), nullable=True)
        definition = str(CreateColumn(column).compile(dialect=conn.dialect))
        conn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {definition}')
        existing.add(name)
        added.append(name)
    return added


def _backfill(conn) -> None:
    table = _quote(conn, _TABLE)
    statements = (
        "data_classification = COALESCE(NULLIF(TRIM(data_classification), ''), 'internal')",
        "requested_provider = COALESCE(NULLIF(TRIM(requested_provider), ''), provider)",
        "authorized_provider = COALESCE(NULLIF(TRIM(authorized_provider), ''), provider)",
        "policy_mode = COALESCE(NULLIF(TRIM(policy_mode), ''), 'off')",
        "policy_decision = COALESCE(NULLIF(TRIM(policy_decision), ''), 'allowed')",
        "policy_reason = COALESCE(NULLIF(TRIM(policy_reason), ''), 'repaired_partial_schema')",
        "policy_correlation_id = COALESCE(NULLIF(TRIM(policy_correlation_id), ''), correlation_id, 'schema-repair')",
        "tenant_id = COALESCE(NULLIF(TRIM(tenant_id), ''), 'legacy')",
        "area_id = COALESCE(NULLIF(TRIM(area_id), ''), 'legacy')",
        "requester_id = COALESCE(NULLIF(TRIM(requester_id), ''), 'legacy-system')",
        "cost_center = COALESCE(NULLIF(TRIM(cost_center), ''), 'legacy')",
    )
    # B608: `table` deriva exclusivamente da constante _TABLE e é escapada pelo dialeto.
    conn.execute(text(f"UPDATE {table} SET {', '.join(statements)}"))  # nosec B608

    rows = conn.execute(
        text(
            # B608: o identificador de tabela é fixo e já foi escapado pelo dialeto.
            f'SELECT id, data_classification FROM {table} '  # nosec B608
            "WHERE classification_lock_sha256 IS NULL OR TRIM(classification_lock_sha256) = ''"
        )
    ).mappings()
    for row in rows:
        digest = hashlib.sha256(
            f"{row['id']}|{row['data_classification']}".encode('utf-8')
        ).hexdigest()
        conn.execute(
            # B608: o único identificador interpolado é a tabela fixa escapada acima.
            text(f'UPDATE {table} SET classification_lock_sha256=:digest WHERE id=:id'),  # nosec B608
            {'digest': digest, 'id': row['id']},
        )


def reconciliar_schema_ai_conversations(engine: Engine) -> dict[str, object]:
    """Repara somente colunas canônicas ausentes em instalações legadas/parciais."""
    with engine.begin() as conn:
        inspector = inspect(conn)
        if _TABLE not in inspector.get_table_names():
            return {'status': 'table_absent', 'added_columns': []}
        added = _add_missing_columns(conn)
        _backfill(conn)
    return {'status': 'ready', 'added_columns': sorted(added)}


def main() -> int:
    from app.db import engine

    result = reconciliar_schema_ai_conversations(engine)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
