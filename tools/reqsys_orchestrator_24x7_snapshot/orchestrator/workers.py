from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .core import (
    ALLOWED_WORKERS,
    IN_PROGRESS,
    PENDING,
    OrchestratorStore,
    WorkItem,
    iso,
    utc_now,
)

AUTO_WORKER_ROLES = ALLOWED_WORKERS - {"human-gate"}
VALID_PROFILES = {"NORMAL", "ESTUDO"}


@dataclass(frozen=True)
class WorkerInfo:
    worker_id: str
    device_name: str
    roles: list[str]
    capabilities: dict[str, Any]
    profile: str
    controller_online: bool
    auth_valid: bool
    controller_version: str
    last_heartbeat: str
    heartbeat_ttl_seconds: int
    correlation_id: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DispatchAssignment:
    item: WorkItem
    worker: WorkerInfo
    dispatch_id: str


class WorkerRegistry:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        OrchestratorStore(self.db_path)
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
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    device_name TEXT NOT NULL,
                    roles_json TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    controller_online INTEGER NOT NULL,
                    auth_valid INTEGER NOT NULL,
                    controller_version TEXT NOT NULL,
                    last_heartbeat TEXT NOT NULL,
                    heartbeat_ttl_seconds INTEGER NOT NULL,
                    correlation_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dispatch_events (
                    dispatch_id TEXT PRIMARY KEY,
                    work_item_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    worker_role TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(work_item_id) REFERENCES work_items(id),
                    FOREIGN KEY(worker_id) REFERENCES workers(worker_id)
                );

                CREATE INDEX IF NOT EXISTS ix_workers_heartbeat
                    ON workers(last_heartbeat, profile);
                CREATE INDEX IF NOT EXISTS ix_dispatch_item
                    ON dispatch_events(work_item_id, occurred_at);
                """
            )

    @staticmethod
    def _validate_text(name: str, value: str, max_length: int = 256) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
        cleaned = value.strip()
        if len(cleaned) > max_length:
            raise ValueError(f"{name} is too long")
        return cleaned

    @staticmethod
    def _validate_roles(roles: list[str]) -> list[str]:
        if not isinstance(roles, list) or not roles:
            raise ValueError("roles must be a non-empty list")
        normalized = sorted(set(roles))
        invalid = [role for role in normalized if role not in AUTO_WORKER_ROLES]
        if invalid:
            raise ValueError(f"unsupported worker roles: {', '.join(invalid)}")
        return normalized

    @staticmethod
    def _validate_capabilities(capabilities: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(capabilities, dict):
            raise ValueError("capabilities must be an object")
        encoded = json.dumps(capabilities, sort_keys=True, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 16384:
            raise ValueError("capabilities payload is too large")
        priority = capabilities.get("dispatch_priority", 100)
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 1000:
            raise ValueError("dispatch_priority must be an integer from 0 to 1000")
        return capabilities

    @staticmethod
    def _row_to_worker(row: sqlite3.Row) -> WorkerInfo:
        return WorkerInfo(
            worker_id=row["worker_id"],
            device_name=row["device_name"],
            roles=json.loads(row["roles_json"]),
            capabilities=json.loads(row["capabilities_json"]),
            profile=row["profile"],
            controller_online=bool(row["controller_online"]),
            auth_valid=bool(row["auth_valid"]),
            controller_version=row["controller_version"],
            last_heartbeat=row["last_heartbeat"],
            heartbeat_ttl_seconds=row["heartbeat_ttl_seconds"],
            correlation_id=row["correlation_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _heartbeat_is_fresh(worker: WorkerInfo, now: datetime | None = None) -> bool:
        reference = now or utc_now()
        heartbeat = datetime.fromisoformat(worker.last_heartbeat)
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=timezone.utc)
        return heartbeat >= reference - timedelta(seconds=worker.heartbeat_ttl_seconds)

    def worker_payload(self, worker: WorkerInfo, now: datetime | None = None) -> dict[str, Any]:
        payload = asdict(worker)
        fresh = self._heartbeat_is_fresh(worker, now)
        payload["fresh"] = fresh
        payload["eligible"] = (
            fresh
            and worker.profile == "NORMAL"
            and worker.controller_online
            and worker.auth_valid
        )
        return payload

    def heartbeat(
        self,
        *,
        worker_id: str,
        device_name: str,
        roles: list[str],
        capabilities: dict[str, Any],
        profile: str,
        controller_online: bool,
        auth_valid: bool,
        controller_version: str,
        correlation_id: str,
        heartbeat_ttl_seconds: int = 120,
    ) -> WorkerInfo:
        worker_id = self._validate_text("worker_id", worker_id)
        device_name = self._validate_text("device_name", device_name)
        correlation_id = self._validate_text("correlation_id", correlation_id)
        controller_version = self._validate_text(
            "controller_version", controller_version, max_length=64
        )
        roles = self._validate_roles(roles)
        capabilities = self._validate_capabilities(capabilities)
        if profile not in VALID_PROFILES:
            raise ValueError("profile must be NORMAL or ESTUDO")
        if not isinstance(controller_online, bool):
            raise ValueError("controller_online must be boolean")
        if not isinstance(auth_valid, bool):
            raise ValueError("auth_valid must be boolean")
        if (
            not isinstance(heartbeat_ttl_seconds, int)
            or isinstance(heartbeat_ttl_seconds, bool)
            or heartbeat_ttl_seconds < 1
            or heartbeat_ttl_seconds > 3600
        ):
            raise ValueError("heartbeat_ttl_seconds must be between 1 and 3600")

        now = iso()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT created_at FROM workers WHERE worker_id = ?", (worker_id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
                INSERT INTO workers (
                    worker_id, device_name, roles_json, capabilities_json, profile,
                    controller_online, auth_valid, controller_version, last_heartbeat,
                    heartbeat_ttl_seconds, correlation_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    device_name = excluded.device_name,
                    roles_json = excluded.roles_json,
                    capabilities_json = excluded.capabilities_json,
                    profile = excluded.profile,
                    controller_online = excluded.controller_online,
                    auth_valid = excluded.auth_valid,
                    controller_version = excluded.controller_version,
                    last_heartbeat = excluded.last_heartbeat,
                    heartbeat_ttl_seconds = excluded.heartbeat_ttl_seconds,
                    correlation_id = excluded.correlation_id,
                    updated_at = excluded.updated_at
                """,
                (
                    worker_id,
                    device_name,
                    json.dumps(roles, sort_keys=True),
                    json.dumps(capabilities, sort_keys=True, ensure_ascii=False),
                    profile,
                    int(controller_online),
                    int(auth_valid),
                    controller_version,
                    now,
                    heartbeat_ttl_seconds,
                    correlation_id,
                    created_at,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM workers WHERE worker_id = ?", (worker_id,)
            ).fetchone()
            conn.commit()
            return self._row_to_worker(row)

    def get_worker(self, worker_id: str) -> WorkerInfo | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workers WHERE worker_id = ?", (worker_id,)
            ).fetchone()
            return self._row_to_worker(row) if row else None

    def list_workers(self) -> list[dict[str, Any]]:
        now = utc_now()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workers ORDER BY device_name, worker_id"
            ).fetchall()
        return [self.worker_payload(self._row_to_worker(row), now) for row in rows]

    @staticmethod
    def _priority(worker: WorkerInfo) -> int:
        return int(worker.capabilities.get("dispatch_priority", 100))

    def _eligible_candidates(
        self,
        conn: sqlite3.Connection,
        role: str,
        now: datetime,
    ) -> list[tuple[WorkerInfo, int]]:
        active_counts = {
            row["lease_owner"]: row["count"]
            for row in conn.execute(
                """
                SELECT lease_owner, COUNT(*) AS count
                FROM work_items
                WHERE status = ? AND lease_owner IS NOT NULL
                GROUP BY lease_owner
                """,
                (IN_PROGRESS,),
            ).fetchall()
        }
        candidates: list[tuple[WorkerInfo, int]] = []
        for row in conn.execute("SELECT * FROM workers").fetchall():
            worker = self._row_to_worker(row)
            if role not in worker.roles:
                continue
            state = self.worker_payload(worker, now)
            if not state["eligible"]:
                continue
            candidates.append((worker, active_counts.get(worker.worker_id, 0)))
        candidates.sort(
            key=lambda pair: (self._priority(pair[0]), pair[1], pair[0].worker_id)
        )
        return candidates

    def _dispatch_row(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        *,
        lease_seconds: int,
        now_dt: datetime,
    ) -> tuple[str, str] | None:
        role = row["target_worker"]
        if role == "human-gate":
            return None
        candidates = self._eligible_candidates(conn, role, now_dt)
        if not candidates:
            return None

        worker = candidates[0][0]
        now = iso(now_dt)
        lease_until = iso(now_dt + timedelta(seconds=lease_seconds))
        changed = conn.execute(
            """
            UPDATE work_items
            SET status = ?, attempts = attempts + 1, lease_owner = ?,
                lease_until = ?, updated_at = ?
            WHERE id = ? AND status = ? AND attempts < max_attempts
            """,
            (IN_PROGRESS, worker.worker_id, lease_until, now, row["id"], PENDING),
        ).rowcount
        if changed != 1:
            return None

        dispatch_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO dispatch_events (
                dispatch_id, work_item_id, worker_id, worker_role,
                correlation_id, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                dispatch_id,
                row["id"],
                worker.worker_id,
                role,
                row["correlation_id"],
                now,
            ),
        )
        return dispatch_id, worker.worker_id

    def dispatch_item(
        self, item_id: str, *, lease_seconds: int = 60
    ) -> DispatchAssignment | None:
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or lease_seconds < 1
            or lease_seconds > 3600
        ):
            raise ValueError("lease_seconds must be between 1 and 3600")

        now_dt = utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM work_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                conn.rollback()
                raise KeyError(item_id)
            if row["status"] != PENDING or row["attempts"] >= row["max_attempts"]:
                conn.commit()
                return None
            dispatched = self._dispatch_row(
                conn, row, lease_seconds=lease_seconds, now_dt=now_dt
            )
            conn.commit()

        if dispatched is None:
            return None
        dispatch_id, worker_id = dispatched
        item = OrchestratorStore(self.db_path).get(item_id)
        worker = self.get_worker(worker_id)
        if item is None or worker is None:
            raise RuntimeError("dispatch state could not be reloaded")
        return DispatchAssignment(item=item, worker=worker, dispatch_id=dispatch_id)

    def dispatch_next(self, *, lease_seconds: int = 60) -> DispatchAssignment | None:
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or lease_seconds < 1
            or lease_seconds > 3600
        ):
            raise ValueError("lease_seconds must be between 1 and 3600")

        now_dt = utc_now()
        selected: tuple[str, str, str] | None = None
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT * FROM work_items
                WHERE status = ? AND attempts < max_attempts
                ORDER BY created_at, id
                """,
                (PENDING,),
            ).fetchall()
            for row in rows:
                dispatched = self._dispatch_row(
                    conn, row, lease_seconds=lease_seconds, now_dt=now_dt
                )
                if dispatched is not None:
                    dispatch_id, worker_id = dispatched
                    selected = (row["id"], dispatch_id, worker_id)
                    break
            conn.commit()

        if selected is None:
            return None
        item_id, dispatch_id, worker_id = selected
        item = OrchestratorStore(self.db_path).get(item_id)
        worker = self.get_worker(worker_id)
        if item is None or worker is None:
            raise RuntimeError("dispatch state could not be reloaded")
        return DispatchAssignment(item=item, worker=worker, dispatch_id=dispatch_id)

    def assigned_items(self, worker_id: str) -> list[WorkItem]:
        worker_id = self._validate_text("worker_id", worker_id)
        now = iso()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM work_items
                WHERE status = ? AND lease_owner = ?
                  AND lease_until IS NOT NULL AND lease_until > ?
                ORDER BY created_at, id
                """,
                (IN_PROGRESS, worker_id, now),
            ).fetchall()
        return [OrchestratorStore._row_to_item(row) for row in rows]

    def snapshot(self) -> dict[str, Any]:
        workers = self.list_workers()
        by_profile: dict[str, int] = {}
        for worker in workers:
            by_profile[worker["profile"]] = by_profile.get(worker["profile"], 0) + 1
        with self._connect() as conn:
            dispatch_count = conn.execute(
                "SELECT COUNT(*) FROM dispatch_events"
            ).fetchone()[0]
        return {
            "total": len(workers),
            "eligible": sum(1 for worker in workers if worker["eligible"]),
            "stale": sum(1 for worker in workers if not worker["fresh"]),
            "by_profile": by_profile,
            "dispatch_events": dispatch_count,
            "workers": workers,
            "generated_at": iso(),
        }
