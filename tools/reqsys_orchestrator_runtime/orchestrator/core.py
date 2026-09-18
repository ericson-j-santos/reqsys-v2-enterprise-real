from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PENDING = "PENDENTE"
IN_PROGRESS = "EM ANDAMENTO"
BLOCKED = "BLOQUEADO"
COMPLETED = "CONCLUÍDO"
CANCELLED = "CANCELADO"
VALID_STATUSES = {PENDING, IN_PROGRESS, BLOCKED, COMPLETED, CANCELLED}

ALLOWED_WORKERS = {
    "planner",
    "builder",
    "ci-remediator",
    "e2e-validator",
    "human-gate",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class RouteDecision:
    worker_role: str
    reason: str


@dataclass(frozen=True)
class WorkItem:
    id: str
    idempotency_key: str
    correlation_id: str
    task_type: str
    payload: dict[str, Any]
    risk: int
    target_worker: str
    status: str
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_until: str | None
    last_error: str | None
    result: dict[str, Any] | None
    created_at: str
    updated_at: str


def route_task(task_type: str, payload: dict[str, Any], risk: int) -> RouteDecision:
    if not isinstance(risk, int) or risk < 0 or risk > 3:
        raise ValueError("risk must be an integer from 0 to 3")

    hint = payload.get("worker_hint")
    if hint is not None:
        if hint not in ALLOWED_WORKERS:
            raise ValueError("worker_hint is not allowed")
        if risk >= 3 and hint != "human-gate":
            return RouteDecision("human-gate", "risk 3 requires human gate")
        return RouteDecision(hint, "explicit validated worker hint")

    normalized = task_type.strip().lower()
    if not normalized:
        raise ValueError("task_type is required")
    if risk >= 3:
        return RouteDecision("human-gate", "risk 3 requires human gate")
    if any(token in normalized for token in ("e2e", "validate", "validation", "evidence")):
        return RouteDecision("e2e-validator", "validation/evidence task")
    if any(token in normalized for token in ("ci", "pipeline", "workflow", "check")):
        return RouteDecision("ci-remediator", "CI/CD task")
    if any(token in normalized for token in ("plan", "spec", "requirement", "design")):
        return RouteDecision("planner", "planning/specification task")
    return RouteDecision("builder", "default implementation route")


class OrchestratorStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS work_items (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    correlation_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    risk INTEGER NOT NULL CHECK (risk BETWEEN 0 AND 3),
                    target_worker TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
                    lease_owner TEXT,
                    lease_until TEXT,
                    last_error TEXT,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS work_events (
                    event_id TEXT PRIMARY KEY,
                    work_item_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(work_item_id) REFERENCES work_items(id)
                );

                CREATE INDEX IF NOT EXISTS ix_work_items_status_worker
                    ON work_items(status, target_worker, created_at);
                CREATE INDEX IF NOT EXISTS ix_work_events_item
                    ON work_events(work_item_id, created_at);
                """
            )

    @staticmethod
    def _validate_identity(event_id: str, correlation_id: str, idempotency_key: str) -> None:
        for name, value in {
            "event_id": event_id,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
            if len(value) > 256:
                raise ValueError(f"{name} is too long")

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> WorkItem:
        return WorkItem(
            id=row["id"],
            idempotency_key=row["idempotency_key"],
            correlation_id=row["correlation_id"],
            task_type=row["task_type"],
            payload=json.loads(row["payload_json"]),
            risk=row["risk"],
            target_worker=row["target_worker"],
            status=row["status"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            lease_owner=row["lease_owner"],
            lease_until=row["lease_until"],
            last_error=row["last_error"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def submit(
        self,
        *,
        event_id: str,
        correlation_id: str,
        idempotency_key: str,
        task_type: str,
        payload: dict[str, Any] | None = None,
        risk: int = 1,
        max_attempts: int = 3,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        self._validate_identity(event_id, correlation_id, idempotency_key)
        if max_attempts < 1 or max_attempts > 20:
            raise ValueError("max_attempts must be between 1 and 20")
        payload = payload or {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        route = route_task(task_type, payload, risk)
        now = iso()
        occurred = occurred_at or now

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = conn.execute(
                "SELECT work_item_id FROM work_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if replay:
                row = conn.execute(
                    "SELECT * FROM work_items WHERE id = ?", (replay["work_item_id"],)
                ).fetchone()
                conn.commit()
                return {
                    "item": self._row_to_item(row),
                    "created": False,
                    "replayed": True,
                    "route_reason": "event replay",
                }

            row = conn.execute(
                "SELECT * FROM work_items WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            created = row is None

            if created:
                item_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO work_items (
                        id, idempotency_key, correlation_id, task_type, payload_json,
                        risk, target_worker, status, attempts, max_attempts,
                        lease_owner, lease_until, last_error, result_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, NULL, ?, ?)
                    """,
                    (
                        item_id,
                        idempotency_key,
                        correlation_id,
                        task_type,
                        json.dumps(payload, sort_keys=True, ensure_ascii=False),
                        risk,
                        route.worker_role,
                        PENDING,
                        max_attempts,
                        now,
                        now,
                    ),
                )
            else:
                item_id = row["id"]
                conn.execute(
                    """
                    UPDATE work_items
                    SET correlation_id = ?, task_type = ?, payload_json = ?, risk = ?,
                        target_worker = ?, max_attempts = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        correlation_id,
                        task_type,
                        json.dumps(payload, sort_keys=True, ensure_ascii=False),
                        risk,
                        route.worker_role,
                        max_attempts,
                        now,
                        item_id,
                    ),
                )

            conn.execute(
                """
                INSERT INTO work_events(event_id, work_item_id, correlation_id, occurred_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, item_id, correlation_id, occurred, now),
            )
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
            conn.commit()
            return {
                "item": self._row_to_item(row),
                "created": created,
                "replayed": False,
                "route_reason": route.reason,
            }

    def lease_next(
        self,
        *,
        worker_role: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> WorkItem | None:
        if worker_role not in ALLOWED_WORKERS:
            raise ValueError("worker_role is not allowed")
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds < 0 or lease_seconds > 3600:
            raise ValueError("lease_seconds must be between 0 and 3600")

        now_dt = utc_now()
        now = iso(now_dt)
        lease_until = iso(now_dt + timedelta(seconds=lease_seconds))

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM work_items
                WHERE status = ? AND target_worker = ? AND attempts < max_attempts
                ORDER BY created_at, id
                LIMIT 1
                """,
                (PENDING, worker_role),
            ).fetchone()
            if row is None:
                conn.commit()
                return None

            changed = conn.execute(
                """
                UPDATE work_items
                SET status = ?, attempts = attempts + 1, lease_owner = ?,
                    lease_until = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (IN_PROGRESS, worker_id, lease_until, now, row["id"], PENDING),
            ).rowcount
            if changed != 1:
                conn.rollback()
                return None
            leased = conn.execute(
                "SELECT * FROM work_items WHERE id = ?", (row["id"],)
            ).fetchone()
            conn.commit()
            return self._row_to_item(leased)

    def complete(self, item_id: str, *, worker_id: str, result: dict[str, Any]) -> WorkItem:
        if not isinstance(result, dict):
            raise ValueError("result must be an object")
        now = iso()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(item_id)
            if row["status"] != IN_PROGRESS:
                conn.rollback()
                raise RuntimeError("work item is not in progress")
            if row["lease_owner"] != worker_id:
                conn.rollback()
                raise PermissionError("lease owner mismatch")
            conn.execute(
                """
                UPDATE work_items
                SET status = ?, result_json = ?, lease_owner = NULL, lease_until = NULL,
                    last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (
                    COMPLETED,
                    json.dumps(result, sort_keys=True, ensure_ascii=False),
                    now,
                    item_id,
                ),
            )
            updated = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
            conn.commit()
            return self._row_to_item(updated)

    def fail(self, item_id: str, *, worker_id: str, error: str) -> WorkItem:
        clean_error = (error or "unspecified failure").strip()[:1000]
        now = iso()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(item_id)
            if row["status"] != IN_PROGRESS:
                conn.rollback()
                raise RuntimeError("work item is not in progress")
            if row["lease_owner"] != worker_id:
                conn.rollback()
                raise PermissionError("lease owner mismatch")
            next_status = BLOCKED if row["attempts"] >= row["max_attempts"] else PENDING
            conn.execute(
                """
                UPDATE work_items
                SET status = ?, lease_owner = NULL, lease_until = NULL,
                    last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_status, clean_error, now, item_id),
            )
            updated = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
            conn.commit()
            return self._row_to_item(updated)

    def recover_expired_leases(self) -> dict[str, int]:
        now = iso()
        recovered = 0
        blocked = 0
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT * FROM work_items
                WHERE status = ? AND lease_until IS NOT NULL AND lease_until <= ?
                """,
                (IN_PROGRESS, now),
            ).fetchall()
            for row in rows:
                next_status = BLOCKED if row["attempts"] >= row["max_attempts"] else PENDING
                if next_status == BLOCKED:
                    blocked += 1
                else:
                    recovered += 1
                conn.execute(
                    """
                    UPDATE work_items
                    SET status = ?, lease_owner = NULL, lease_until = NULL,
                        last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        next_status,
                        "lease expired",
                        now,
                        row["id"],
                    ),
                )
            conn.commit()
        return {"recovered": recovered, "blocked": blocked}

    def get(self, item_id: str) -> WorkItem | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
            return self._row_to_item(row) if row else None

    def snapshot(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM work_items").fetchone()[0]
            by_status = {
                row["status"]: row["count"]
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS count FROM work_items GROUP BY status"
                ).fetchall()
            }
            by_worker = {
                row["target_worker"]: row["count"]
                for row in conn.execute(
                    """
                    SELECT target_worker, COUNT(*) AS count
                    FROM work_items
                    WHERE status IN (?, ?, ?)
                    GROUP BY target_worker
                    """,
                    (PENDING, IN_PROGRESS, BLOCKED),
                ).fetchall()
            }
            blockers = [
                {
                    "id": row["id"],
                    "correlation_id": row["correlation_id"],
                    "target_worker": row["target_worker"],
                    "last_error": row["last_error"],
                    "attempts": row["attempts"],
                }
                for row in conn.execute(
                    """
                    SELECT id, correlation_id, target_worker, last_error, attempts
                    FROM work_items
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT 20
                    """,
                    (BLOCKED,),
                ).fetchall()
            ]
            return {
                "total": total,
                "by_status": by_status,
                "by_worker": by_worker,
                "blockers": blockers,
                "generated_at": iso(),
            }

    def event_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM work_events").fetchone()[0]
