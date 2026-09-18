from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

STATES = ("queued", "leased", "running", "validating", "blocked", "completed", "failed")
ACTIVE = ("leased", "running", "validating")
ROLES = ("builder", "validator")
PROFILES = ("NORMAL", "ESTUDO")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
SECRET = re.compile(r"(?i)\b(token|secret|password|passwd|dsn|connection[_-]?string|api[_-]?key)\s*[:=]\s*[^\s,;]+")


class PoolError(RuntimeError):
    pass


class NotFoundError(PoolError):
    pass


class ConflictError(PoolError):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def sanitize(value: str) -> str:
    value = BEARER.sub("Bearer [REDACTED]", value)
    return SECRET.sub(lambda m: f"{m.group(1)}=[REDACTED]", value)[:1000]


def identity(repository: str, issue_number: int, request_id: str) -> str:
    raw = f"{repository.strip().lower()}|{int(issue_number)}|{request_id.strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()


build_idempotency_key = identity


def task_id(key: str) -> str:
    return f"cwp-{key[:24]}"


def branch(issue_number: int, request_id: str) -> str:
    return f"codex/issue-{issue_number}-{hashlib.sha256(request_id.encode()).hexdigest()[:10]}"


def workspace(repository: str, task: str) -> str:
    return "worker-" + hashlib.sha256(f"{repository}|{task}".encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Lease:
    task_id: str
    lease_token: str
    worker_id: str
    role: str
    lease_expires_at: str


class WorkerPoolStore:
    def __init__(
        self,
        db_path: str | Path,
        *,
        clock: Callable[[], datetime] = now_utc,
        heartbeat_ttl_seconds: int = 90,
        default_lease_seconds: int = 120,
        default_max_attempts: int = 3,
    ) -> None:
        if min(heartbeat_ttl_seconds, default_lease_seconds, default_max_attempts) < 1:
            raise ValueError("timeouts e tentativas devem ser positivos")
        self.db_path, self.clock = Path(db_path), clock
        self.heartbeat_ttl_seconds = heartbeat_ttl_seconds
        self.default_lease_seconds = default_lease_seconds
        self.default_max_attempts = default_max_attempts
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = threading.Lock()
        self._init()

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        db = self._db()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _init(self) -> None:
        with self._init_lock, self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS workers(
              worker_id TEXT PRIMARY KEY, host TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('builder','validator')),
              profile TEXT NOT NULL CHECK(profile IN ('NORMAL','ESTUDO')),
              capacity_score INTEGER NOT NULL DEFAULT 50,
              controller_version TEXT, rules_sha TEXT,
              gateway_ok INTEGER NOT NULL DEFAULT 0,
              state_validated INTEGER NOT NULL DEFAULT 0,
              worktree_root TEXT, registered_at TEXT NOT NULL,
              last_heartbeat_at TEXT NOT NULL, cpu_percent REAL,
              memory_percent REAL, correlation_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks(
              task_id TEXT PRIMARY KEY, repository TEXT NOT NULL,
              issue_number INTEGER NOT NULL, request_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              state TEXT NOT NULL CHECK(state IN
                ('queued','leased','running','validating','blocked','completed','failed')),
              priority INTEGER NOT NULL, branch TEXT NOT NULL,
              workspace_key TEXT NOT NULL, base_sha TEXT, produced_sha TEXT,
              builder_worker_id TEXT, validator_worker_id TEXT, leased_by TEXT,
              lease_token TEXT, lease_expires_at TEXT,
              attempt_count INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL, blocked_reason TEXT, last_error TEXT,
              correlation_id TEXT NOT NULL, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL, completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS quarantine(
              id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL, correlation_id TEXT NOT NULL,
              attempt_count INTEGER NOT NULL, reason TEXT NOT NULL,
              quarantined_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_task_queue
              ON tasks(state,priority,created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_worker_active
              ON tasks(leased_by)
              WHERE leased_by IS NOT NULL AND state IN ('leased','running','validating');
            CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_active
              ON tasks(repository,workspace_key)
              WHERE state IN ('leased','running','validating');
            """)

    @staticmethod
    def _d(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise NotFoundError("registro não encontrado")
        return dict(row)

    def register_worker(
        self, *, worker_id: str, host: str, role: str, correlation_id: str,
        profile: str = "NORMAL", capacity_score: int = 50,
        controller_version: str | None = None, rules_sha: str | None = None,
        gateway_ok: bool = False, state_validated: bool = False,
        worktree_root: str | None = None,
    ) -> dict[str, Any]:
        role, profile = role.lower(), profile.upper()
        if not worker_id.strip() or not host.strip() or not correlation_id.strip():
            raise ValueError("worker_id, host e correlation_id são obrigatórios")
        if role not in ROLES or profile not in PROFILES:
            raise ValueError("role/profile inválido")
        stamp = iso(self.clock())
        with self._tx() as db:
            db.execute("""INSERT INTO workers VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(worker_id) DO UPDATE SET
              host=excluded.host,role=excluded.role,profile=excluded.profile,
              capacity_score=excluded.capacity_score,
              controller_version=excluded.controller_version,rules_sha=excluded.rules_sha,
              gateway_ok=excluded.gateway_ok,state_validated=excluded.state_validated,
              worktree_root=excluded.worktree_root,last_heartbeat_at=excluded.last_heartbeat_at,
              correlation_id=excluded.correlation_id""",
              (worker_id.strip(), host.strip(), role, profile, int(capacity_score),
               controller_version, rules_sha, int(gateway_ok), int(state_validated),
               worktree_root, stamp, stamp, None, None, correlation_id.strip()))
        return self.get_worker(worker_id)

    def get_worker(self, worker_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM workers WHERE worker_id=?", (worker_id,)).fetchone()
        data = self._d(row)
        data["gateway_ok"], data["state_validated"] = bool(data["gateway_ok"]), bool(data["state_validated"])
        return data

    def heartbeat_worker(
        self, worker_id: str, *, correlation_id: str, profile: str | None = None,
        cpu_percent: float | None = None, memory_percent: float | None = None,
        gateway_ok: bool | None = None, state_validated: bool | None = None,
    ) -> dict[str, Any]:
        current = self.get_worker(worker_id)
        profile = (profile or current["profile"]).upper()
        if profile not in PROFILES:
            raise ValueError("profile inválido")
        with self._tx() as db:
            db.execute("""UPDATE workers SET profile=?,last_heartbeat_at=?,cpu_percent=?,
              memory_percent=?,gateway_ok=?,state_validated=?,correlation_id=? WHERE worker_id=?""",
              (profile, iso(self.clock()), cpu_percent, memory_percent,
               int(current["gateway_ok"] if gateway_ok is None else gateway_ok),
               int(current["state_validated"] if state_validated is None else state_validated),
               correlation_id, worker_id))
        return self.get_worker(worker_id)

    def enqueue_task(
        self, *, repository: str, issue_number: int, request_id: str,
        correlation_id: str, priority: int = 100, base_sha: str | None = None,
        max_attempts: int | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if "/" not in repository or issue_number < 1 or not request_id.strip() or not correlation_id.strip():
            raise ValueError("identidade da task inválida")
        if base_sha and not SHA40.fullmatch(base_sha.lower()):
            raise ValueError("base_sha inválido")
        key, stamp = identity(repository, issue_number, request_id), iso(self.clock())
        tid, attempts = task_id(key), int(max_attempts or self.default_max_attempts)
        if attempts < 1:
            raise ValueError("max_attempts inválido")
        with self._tx() as db:
            row = db.execute("SELECT * FROM tasks WHERE idempotency_key=?", (key,)).fetchone()
            created = row is None
            if created:
                db.execute("""INSERT INTO tasks(
                  task_id,repository,issue_number,request_id,idempotency_key,state,priority,
                  branch,workspace_key,base_sha,max_attempts,correlation_id,created_at,updated_at)
                  VALUES(?,?,?,?,?,'queued',?,?,?,?,?,?,?,?)""",
                  (tid, repository.strip(), issue_number, request_id.strip(), key, int(priority),
                   branch(issue_number, request_id), workspace(repository, tid),
                   base_sha.lower() if base_sha else None, attempts,
                   correlation_id.strip(), stamp, stamp))
                row = db.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
        return self._d(row), created

    def _ready(self, db: sqlite3.Connection, worker_id: str, role: str) -> sqlite3.Row:
        w = db.execute("SELECT * FROM workers WHERE worker_id=?", (worker_id,)).fetchone()
        if not w:
            raise NotFoundError(f"worker não encontrado: {worker_id}")
        if w["role"] != role:
            raise ConflictError(f"worker {worker_id} não possui role {role}")
        if w["profile"] != "NORMAL":
            raise ConflictError(f"worker {worker_id} está em profile {w['profile']}")
        if not w["gateway_ok"] or not w["state_validated"]:
            raise ConflictError("worker não está governado/pronto")
        if (self.clock() - parse_iso(w["last_heartbeat_at"])).total_seconds() > self.heartbeat_ttl_seconds:
            raise ConflictError("worker está offline/stale")
        if db.execute("SELECT 1 FROM tasks WHERE leased_by=? AND state IN ('leased','running','validating')", (worker_id,)).fetchone():
            raise ConflictError("worker já possui task ativa")
        return w

    def _quarantine(self, db: sqlite3.Connection, row: sqlite3.Row, reason: str, stamp: str) -> None:
        db.execute("""INSERT INTO quarantine(task_id,idempotency_key,correlation_id,
          attempt_count,reason,quarantined_at) VALUES(?,?,?,?,?,?)""",
          (row["task_id"], row["idempotency_key"], row["correlation_id"],
           row["attempt_count"], sanitize(reason), stamp))

    def _recover(self, db: sqlite3.Connection) -> int:
        stamp = iso(self.clock())
        rows = db.execute("""SELECT * FROM tasks WHERE state IN ('leased','running','validating')
          AND lease_expires_at IS NOT NULL AND lease_expires_at<=?""", (stamp,)).fetchall()
        for row in rows:
            if row["attempt_count"] >= row["max_attempts"]:
                self._quarantine(db, row, "lease_expired_max_attempts", stamp)
                state = "failed"
            else:
                state = "validating" if row["produced_sha"] else "queued"
            db.execute("""UPDATE tasks SET state=?,leased_by=NULL,lease_token=NULL,
              lease_expires_at=NULL,last_error='lease_expired_recovered',updated_at=?
              WHERE task_id=?""", (state, stamp, row["task_id"]))
        return len(rows)

    def claim_task(
        self, *, worker_id: str, role: str, correlation_id: str,
        lease_seconds: int | None = None,
    ) -> tuple[dict[str, Any] | None, Lease | None]:
        role, ttl = role.lower(), int(lease_seconds or self.default_lease_seconds)
        if role not in ROLES or ttl < 1:
            raise ValueError("role/lease inválido")
        now, stamp = self.clock(), iso(self.clock())
        with self._tx() as db:
            self._recover(db)
            self._ready(db, worker_id, role)
            if role == "builder":
                row = db.execute("""SELECT * FROM tasks WHERE state='queued'
                  ORDER BY priority,created_at,task_id LIMIT 1""").fetchone()
                wanted, next_state = "queued", "leased"
            else:
                row = db.execute("""SELECT * FROM tasks WHERE state='validating'
                  AND leased_by IS NULL AND produced_sha IS NOT NULL
                  AND (builder_worker_id IS NULL OR builder_worker_id<>?)
                  ORDER BY priority,updated_at,task_id LIMIT 1""", (worker_id,)).fetchone()
                wanted, next_state = "validating", "validating"
            if not row:
                return None, None
            token, expires = uuid.uuid4().hex, iso(now + timedelta(seconds=ttl))
            validator = worker_id if role == "validator" else row["validator_worker_id"]
            cur = db.execute("""UPDATE tasks SET state=?,leased_by=?,lease_token=?,
              lease_expires_at=?,attempt_count=attempt_count+1,validator_worker_id=?,
              correlation_id=?,updated_at=? WHERE task_id=? AND state=? AND leased_by IS NULL""",
              (next_state, worker_id, token, expires, validator, correlation_id,
               stamp, row["task_id"], wanted))
            if cur.rowcount != 1:
                raise ConflictError("task adquirida concorrentemente")
            row = db.execute("SELECT * FROM tasks WHERE task_id=?", (row["task_id"],)).fetchone()
        data = self._d(row)
        return data, Lease(data["task_id"], token, worker_id, role, expires)

    def _lease(self, db: sqlite3.Connection, tid: str, worker: str, token: str, allowed: tuple[str, ...]) -> sqlite3.Row:
        row = db.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
        if not row:
            raise NotFoundError(f"task não encontrada: {tid}")
        if row["state"] not in allowed:
            raise ConflictError(f"estado inválido: {row['state']}")
        if row["leased_by"] != worker or row["lease_token"] != token:
            raise ConflictError("lease inválido")
        if not row["lease_expires_at"] or parse_iso(row["lease_expires_at"]) <= self.clock():
            raise ConflictError("lease expirado")
        return row

    def renew_lease(self, *, task_id: str, worker_id: str, lease_token: str,
                    correlation_id: str, lease_seconds: int | None = None) -> dict[str, Any]:
        expires = iso(self.clock() + timedelta(seconds=int(lease_seconds or self.default_lease_seconds)))
        with self._tx() as db:
            self._lease(db, task_id, worker_id, lease_token, ACTIVE)
            db.execute("UPDATE tasks SET lease_expires_at=?,correlation_id=?,updated_at=? WHERE task_id=?",
                       (expires, correlation_id, iso(self.clock()), task_id))
        return self.get_task(task_id)

    def start_task(self, *, task_id: str, worker_id: str, lease_token: str, correlation_id: str) -> dict[str, Any]:
        with self._tx() as db:
            self._lease(db, task_id, worker_id, lease_token, ("leased",))
            if self.get_worker(worker_id)["role"] != "builder":
                raise ConflictError("somente Builder pode iniciar task")
            db.execute("""UPDATE tasks SET state='running',builder_worker_id=?,
              correlation_id=?,updated_at=? WHERE task_id=?""",
              (worker_id, correlation_id, iso(self.clock()), task_id))
        return self.get_task(task_id)

    def submit_for_validation(
        self, *, task_id: str, worker_id: str, lease_token: str,
        produced_sha: str, correlation_id: str,
    ) -> dict[str, Any]:
        produced_sha = produced_sha.lower()
        if not SHA40.fullmatch(produced_sha):
            raise ValueError("produced_sha inválido")
        with self._tx() as db:
            row = self._lease(db, task_id, worker_id, lease_token, ("running",))
            if row["builder_worker_id"] != worker_id:
                raise ConflictError("builder divergente")
            db.execute("""UPDATE tasks SET state='validating',produced_sha=?,leased_by=NULL,
              lease_token=NULL,lease_expires_at=NULL,correlation_id=?,updated_at=? WHERE task_id=?""",
              (produced_sha, correlation_id, iso(self.clock()), task_id))
        return self.get_task(task_id)

    def complete_task(self, *, task_id: str, worker_id: str, lease_token: str, correlation_id: str) -> dict[str, Any]:
        with self._tx() as db:
            row = self._lease(db, task_id, worker_id, lease_token, ("validating",))
            if self.get_worker(worker_id)["role"] != "validator" or row["builder_worker_id"] == worker_id:
                raise ConflictError("Validator independente obrigatório")
            if not row["produced_sha"]:
                raise ConflictError("task sem produced_sha")
            stamp = iso(self.clock())
            db.execute("""UPDATE tasks SET state='completed',leased_by=NULL,lease_token=NULL,
              lease_expires_at=NULL,correlation_id=?,updated_at=?,completed_at=? WHERE task_id=?""",
              (correlation_id, stamp, stamp, task_id))
        return self.get_task(task_id)

    def fail_task(self, *, task_id: str, worker_id: str, lease_token: str,
                  correlation_id: str, reason: str) -> dict[str, Any]:
        reason, stamp = sanitize(reason.strip()) or "worker_failure", iso(self.clock())
        with self._tx() as db:
            row = self._lease(db, task_id, worker_id, lease_token, ACTIVE)
            if row["attempt_count"] >= row["max_attempts"]:
                state = "failed"
                self._quarantine(db, row, reason, stamp)
            else:
                state = "validating" if row["produced_sha"] else "queued"
            db.execute("""UPDATE tasks SET state=?,leased_by=NULL,lease_token=NULL,
              lease_expires_at=NULL,last_error=?,correlation_id=?,updated_at=? WHERE task_id=?""",
              (state, reason, correlation_id, stamp, task_id))
        return self.get_task(task_id)

    def block_task(self, *, task_id: str, worker_id: str, lease_token: str,
                   correlation_id: str, reason: str) -> dict[str, Any]:
        reason = sanitize(reason.strip())
        if not reason:
            raise ValueError("reason obrigatório")
        with self._tx() as db:
            self._lease(db, task_id, worker_id, lease_token, ACTIVE)
            db.execute("""UPDATE tasks SET state='blocked',leased_by=NULL,lease_token=NULL,
              lease_expires_at=NULL,blocked_reason=?,correlation_id=?,updated_at=? WHERE task_id=?""",
              (reason, correlation_id, iso(self.clock()), task_id))
        return self.get_task(task_id)

    def requeue_blocked(self, task_id: str, *, correlation_id: str) -> dict[str, Any]:
        with self._tx() as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if not row:
                raise NotFoundError(f"task não encontrada: {task_id}")
            if row["state"] != "blocked":
                raise ConflictError("somente task bloqueada pode ser reenfileirada")
            state = "validating" if row["produced_sha"] else "queued"
            db.execute("""UPDATE tasks SET state=?,blocked_reason=NULL,
              correlation_id=?,updated_at=? WHERE task_id=?""",
              (state, correlation_id, iso(self.clock()), task_id))
        return self.get_task(task_id)

    def recover_expired_leases(self) -> int:
        with self._tx() as db:
            return self._recover(db)

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._db() as db:
            return self._d(db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone())

    def list_quarantine(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return [dict(r) for r in db.execute("""SELECT task_id,idempotency_key,
              correlation_id,attempt_count,reason,quarantined_at
              FROM quarantine ORDER BY id DESC""").fetchall()]

    def snapshot(self) -> dict[str, Any]:
        self.recover_expired_leases()
        now = self.clock()
        with self._db() as db:
            workers = db.execute("SELECT * FROM workers ORDER BY host,worker_id").fetchall()
            tasks = db.execute("""SELECT * FROM tasks WHERE state<>'completed'
              ORDER BY priority,created_at,task_id""").fetchall()
            counts = {r["state"]: r["n"] for r in db.execute(
                "SELECT state,COUNT(*) n FROM tasks GROUP BY state").fetchall()}
            qn = db.execute("SELECT COUNT(*) n FROM quarantine").fetchone()["n"]
        active = {r["leased_by"]: dict(r) for r in tasks if r["leased_by"]}
        views = []
        for row in workers:
            w, age = dict(row), max(0.0, (now - parse_iso(row["last_heartbeat_at"])).total_seconds())
            online, task = age <= self.heartbeat_ttl_seconds, active.get(row["worker_id"])
            if not online: why = "offline_or_stale"
            elif row["profile"] == "ESTUDO": why = "profile_estudo"
            elif not row["gateway_ok"] or not row["state_validated"]: why = "governance_not_ready"
            elif task: why = None
            elif row["role"] == "builder" and not counts.get("queued", 0): why = "no_queued_work"
            elif row["role"] == "validator" and not counts.get("validating", 0): why = "no_validation_work"
            else: why = "available"
            w.update(gateway_ok=bool(w["gateway_ok"]), state_validated=bool(w["state_validated"]),
                     online=online, heartbeat_age_seconds=round(age, 3),
                     active_task=task["task_id"] if task else None,
                     active_sha=task["produced_sha"] if task else None, why_idle=why)
            views.append(w)
        safe = ("task_id","repository","issue_number","state","priority","branch","workspace_key",
                "base_sha","produced_sha","builder_worker_id","validator_worker_id","leased_by",
                "lease_expires_at","attempt_count","max_attempts","blocked_reason","last_error",
                "correlation_id","updated_at")
        return {
            "schema_version":"1.0.0", "generated_at":iso(now), "workers":views,
            "queue":{s:counts.get(s,0) for s in STATES}, "quarantine_count":qn,
            "tasks":[{k:r[k] for k in safe} for r in tasks],
        }
