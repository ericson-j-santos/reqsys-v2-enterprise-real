from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = ROOT / "config" / "operational-orchestrator" / "dev.yaml"
DEFAULT_DB_PATH = Path(
    os.getenv("REQSYS_OPERATIONAL_DB_PATH")
    or Path(tempfile.gettempdir()) / "reqsys-operational-orchestrator" / "state.sqlite3"
)

_ALLOWED_RISKS = {"green", "yellow", "red"}
_ALLOWED_STATUSES = {"ready", "awaiting_approval", "running", "succeeded", "blocked", "failed"}
_AUTO_EXECUTORS = {"readiness_check"}
_SENSITIVE_KEY_MARKERS = ("token", "secret", "password", "authorization", "api_key", "credential")


class OperationalOrchestratorError(RuntimeError):
    """Erro de domínio do Operational Orchestrator."""


class ManifestError(OperationalOrchestratorError):
    """Manifesto de readiness inválido."""


@dataclass(frozen=True)
class OperationalAction:
    action_id: str
    idempotency_key: str
    source: str
    project: str
    environment: str
    action_type: str
    repository: str | None
    branch: str | None
    sha: str | None
    risk: str
    status: str
    executor: str
    next_action: str
    validation: dict[str, Any]
    correlation_id: str
    payload: dict[str, Any]
    attempts: int
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    idempotency_key: str
    action_id: str
    correlation_id: str
    environment: str
    branch: str | None
    sha: str | None
    kind: str
    status: str
    source: str
    observed_at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _assert_safe_metadata(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS):
                raise OperationalOrchestratorError(
                    f"Metadado sensível não permitido em {path}.{key}; grave apenas referência, nunca o valor."
                )
            _assert_safe_metadata(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_safe_metadata(child, path=f"{path}[{index}]")


def load_readiness_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    if not path.exists():
        raise ManifestError(f"Manifesto de readiness ausente: {path}")

    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ManifestError(
                "O manifesto não usa sintaxe JSON/YAML compatível com a biblioteca padrão; instale PyYAML."
            ) from exc
        payload = yaml.safe_load(text)

    if not isinstance(payload, dict):
        raise ManifestError("O manifesto deve conter um objeto no nível raiz.")
    if not isinstance(payload.get("environment"), str) or not payload["environment"].strip():
        raise ManifestError("environment é obrigatório.")
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities:
        raise ManifestError("capabilities deve ser um objeto não vazio.")

    for name, config in capabilities.items():
        if not isinstance(config, dict):
            raise ManifestError(f"capabilities.{name} deve ser um objeto.")
        if not isinstance(config.get("required"), bool):
            raise ManifestError(f"capabilities.{name}.required deve ser booleano.")
        source = config.get("source")
        if source not in {"env", "static"}:
            raise ManifestError(f"capabilities.{name}.source deve ser env ou static.")
        if source == "env":
            refs = config.get("references")
            if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item for item in refs):
                raise ManifestError(f"capabilities.{name}.references deve ser uma lista não vazia.")
        if source == "static" and not isinstance(config.get("configured"), bool):
            raise ManifestError(f"capabilities.{name}.configured deve ser booleano para source=static.")
        forbidden = set(config).intersection({"value", "password", "token", "secret", "credential"})
        if forbidden:
            raise ManifestError(
                f"capabilities.{name} contém campos proibidos: {', '.join(sorted(forbidden))}."
            )
    return payload


def evaluate_readiness(
    manifest: dict[str, Any],
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    checks: list[dict[str, Any]] = []
    missing_required: list[str] = []

    for name, config in manifest["capabilities"].items():
        source = config["source"]
        references = list(config.get("references") or [])
        missing_references: list[str] = []
        if source == "env":
            missing_references = [ref for ref in references if not str(env.get(ref, "")).strip()]
            configured = not missing_references
        else:
            configured = bool(config.get("configured"))

        required = bool(config["required"])
        if required and not configured:
            missing_required.append(name)

        checks.append(
            {
                "capability": name,
                "required": required,
                "configured": configured,
                "source": source,
                "references": references,
                "missing_references": missing_references,
                "description": str(config.get("description") or ""),
            }
        )

    return {
        "environment": manifest["environment"],
        "status": "ready" if not missing_required else "blocked",
        "required_total": sum(1 for item in checks if item["required"]),
        "configured_required": sum(1 for item in checks if item["required"] and item["configured"]),
        "missing_required": missing_required,
        "checks": checks,
    }


class OperationalStore:
    """Persistência SQLite para Action Queue e Evidence Ledger.

    Evidence Ledger é append-only por contrato: não há métodos de update/delete de evidência.
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    action_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    project TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    repository TEXT,
                    branch TEXT,
                    sha TEXT,
                    risk TEXT NOT NULL,
                    status TEXT NOT NULL,
                    executor TEXT NOT NULL,
                    next_action TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    correlation_id TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
                CREATE INDEX IF NOT EXISTS idx_actions_sha ON actions(sha);

                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    action_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    branch TEXT,
                    sha TEXT,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(action_id) REFERENCES actions(action_id)
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_correlation ON evidence(correlation_id);
                CREATE INDEX IF NOT EXISTS idx_evidence_sha ON evidence(sha);
                """
            )

    @staticmethod
    def _action_from_row(row: sqlite3.Row) -> OperationalAction:
        return OperationalAction(
            action_id=row["action_id"],
            idempotency_key=row["idempotency_key"],
            source=row["source"],
            project=row["project"],
            environment=row["environment"],
            action_type=row["action_type"],
            repository=row["repository"],
            branch=row["branch"],
            sha=row["sha"],
            risk=row["risk"],
            status=row["status"],
            executor=row["executor"],
            next_action=row["next_action"],
            validation=json.loads(row["validation_json"]),
            correlation_id=row["correlation_id"],
            payload=json.loads(row["payload_json"]),
            attempts=int(row["attempts"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=row["evidence_id"],
            idempotency_key=row["idempotency_key"],
            action_id=row["action_id"],
            correlation_id=row["correlation_id"],
            environment=row["environment"],
            branch=row["branch"],
            sha=row["sha"],
            kind=row["kind"],
            status=row["status"],
            source=row["source"],
            observed_at=row["observed_at"],
            payload=json.loads(row["payload_json"]),
        )

    def enqueue(
        self,
        *,
        source: str,
        project: str,
        environment: str,
        action_type: str,
        repository: str | None,
        branch: str | None,
        sha: str | None,
        risk: str,
        executor: str,
        next_action: str,
        validation: dict[str, Any],
        payload: dict[str, Any],
        idempotency_material: dict[str, Any] | None = None,
    ) -> tuple[OperationalAction, bool]:
        if risk not in _ALLOWED_RISKS:
            raise OperationalOrchestratorError(f"Risco inválido: {risk}")
        _assert_safe_metadata(payload)
        _assert_safe_metadata(validation, path="validation")

        material = idempotency_material or {
            "source": source,
            "project": project,
            "environment": environment,
            "action_type": action_type,
            "repository": repository,
            "branch": branch,
            "sha": sha,
            "payload": payload,
        }
        key = _sha256(material)
        action_id = f"ACT-{key[:20]}"
        correlation_id = f"REQSYS-ACT-{key[:16]}"
        initial_status = "ready" if risk == "green" else ("awaiting_approval" if risk == "yellow" else "blocked")
        now = _utc_now()

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM actions WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing:
                return self._action_from_row(existing), False

            conn.execute(
                """
                INSERT INTO actions (
                    action_id, idempotency_key, source, project, environment, action_type,
                    repository, branch, sha, risk, status, executor, next_action,
                    validation_json, correlation_id, payload_json, attempts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    action_id,
                    key,
                    source,
                    project,
                    environment,
                    action_type,
                    repository,
                    branch,
                    sha,
                    risk,
                    initial_status,
                    executor,
                    next_action,
                    _canonical_json(validation),
                    correlation_id,
                    _canonical_json(payload),
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM actions WHERE action_id = ?", (action_id,)).fetchone()
            assert row is not None
            return self._action_from_row(row), True

    def get_action(self, action_id: str) -> OperationalAction | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM actions WHERE action_id = ?", (action_id,)).fetchone()
        return self._action_from_row(row) if row else None

    def list_actions(self, status: str | None = None, limit: int = 100) -> list[OperationalAction]:
        bounded = max(1, min(limit, 500))
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM actions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, bounded),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM actions ORDER BY created_at DESC LIMIT ?", (bounded,)
                ).fetchall()
        return [self._action_from_row(row) for row in rows]

    def set_action_status(self, action_id: str, status: str, *, increment_attempts: bool = False) -> OperationalAction:
        if status not in _ALLOWED_STATUSES:
            raise OperationalOrchestratorError(f"Status inválido: {status}")
        now = _utc_now()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM actions WHERE action_id = ?", (action_id,)).fetchone()
            if not row:
                raise KeyError(action_id)
            attempts = int(row["attempts"]) + (1 if increment_attempts else 0)
            conn.execute(
                "UPDATE actions SET status = ?, attempts = ?, updated_at = ? WHERE action_id = ?",
                (status, attempts, now, action_id),
            )
            updated = conn.execute("SELECT * FROM actions WHERE action_id = ?", (action_id,)).fetchone()
            assert updated is not None
            return self._action_from_row(updated)

    def append_evidence(
        self,
        action: OperationalAction,
        *,
        kind: str,
        status: str,
        source: str,
        payload: dict[str, Any],
    ) -> tuple[EvidenceRecord, bool]:
        _assert_safe_metadata(payload)
        material = {
            "action_id": action.action_id,
            "kind": kind,
            "status": status,
            "source": source,
            "payload": payload,
        }
        key = _sha256(material)
        evidence_id = f"EVD-{key[:20]}"
        observed_at = _utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM evidence WHERE idempotency_key = ?", (key,)
            ).fetchone()
            if existing:
                return self._evidence_from_row(existing), False
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, idempotency_key, action_id, correlation_id, environment,
                    branch, sha, kind, status, source, observed_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    key,
                    action.action_id,
                    action.correlation_id,
                    action.environment,
                    action.branch,
                    action.sha,
                    kind,
                    status,
                    source,
                    observed_at,
                    _canonical_json(payload),
                ),
            )
            row = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
            assert row is not None
            return self._evidence_from_row(row), True

    def list_evidence(self, correlation_id: str | None = None, limit: int = 200) -> list[EvidenceRecord]:
        bounded = max(1, min(limit, 1000))
        with self._connect() as conn:
            if correlation_id:
                rows = conn.execute(
                    "SELECT * FROM evidence WHERE correlation_id = ? ORDER BY observed_at DESC LIMIT ?",
                    (correlation_id, bounded),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM evidence ORDER BY observed_at DESC LIMIT ?", (bounded,)
                ).fetchall()
        return [self._evidence_from_row(row) for row in rows]

    def summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            action_rows = conn.execute(
                "SELECT status, COUNT(*) AS total FROM actions GROUP BY status"
            ).fetchall()
            evidence_total = int(conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0])
        by_status = {row["status"]: int(row["total"]) for row in action_rows}
        return {
            "actions_total": sum(by_status.values()),
            "actions_by_status": by_status,
            "evidence_total": evidence_total,
        }


class OperationalOrchestrator:
    def __init__(
        self,
        *,
        store: OperationalStore | None = None,
        manifest_path: Path | str = DEFAULT_MANIFEST,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.store = store or OperationalStore()
        self.manifest_path = Path(manifest_path)
        self.environ = os.environ if environ is None else environ

    def readiness(self) -> dict[str, Any]:
        return evaluate_readiness(load_readiness_manifest(self.manifest_path), self.environ)

    def enqueue_readiness_check(
        self,
        *,
        sha: str,
        branch: str = "main",
        project: str = "reqsys",
        repository: str = "ericson-j-santos/reqsys-v2-enterprise-real",
    ) -> tuple[OperationalAction, bool]:
        manifest = load_readiness_manifest(self.manifest_path)
        environment = str(manifest["environment"])
        return self.store.enqueue(
            source="readiness_as_code",
            project=project,
            environment=environment,
            action_type="readiness_check",
            repository=repository,
            branch=branch,
            sha=sha,
            risk="green",
            executor="readiness_check",
            next_action="executar_readiness_e_registrar_evidencia",
            validation={
                "required": True,
                "e2e": True,
                "independent_evidence": True,
                "idempotency": True,
            },
            payload={"manifest": self.manifest_path.as_posix()},
            idempotency_material={
                "type": "readiness_check",
                "environment": environment,
                "repository": repository,
                "branch": branch,
                "sha": sha,
            },
        )

    def ingest_workflow_run(
        self,
        workflow_run: dict[str, Any],
        *,
        project: str = "reqsys",
        environment: str = "development",
    ) -> dict[str, Any]:
        status = str(workflow_run.get("status") or "unknown")
        conclusion = workflow_run.get("conclusion")
        if status != "completed":
            return {"created": False, "reason": "run_not_terminal"}
        if conclusion == "success":
            return {"created": False, "reason": "healthy_run"}

        payload = {
            "run_id": workflow_run.get("id"),
            "workflow": str(workflow_run.get("name") or workflow_run.get("workflow_name") or "unknown"),
            "conclusion": conclusion,
            "event": workflow_run.get("event"),
            "html_url": workflow_run.get("html_url"),
        }
        action, created = self.store.enqueue(
            source="github_actions",
            project=project,
            environment=environment,
            action_type="ci_failure",
            repository=str(workflow_run.get("repository") or "ericson-j-santos/reqsys-v2-enterprise-real"),
            branch=workflow_run.get("head_branch"),
            sha=workflow_run.get("head_sha"),
            risk="yellow",
            executor="github_agent",
            next_action="analisar_causa_raiz_e_corrigir_menor_incremento_no_mesmo_pr",
            validation={
                "required": True,
                "e2e": True,
                "independent_evidence": True,
                "revalidate_new_sha": True,
            },
            payload=payload,
            idempotency_material={
                "type": "ci_failure",
                "run_id": workflow_run.get("id"),
                "head_sha": workflow_run.get("head_sha"),
                "conclusion": conclusion,
            },
        )
        return {"created": created, "action": action.to_dict()}

    def execute(self, action_id: str, *, confirm: bool = False) -> dict[str, Any]:
        action = self.store.get_action(action_id)
        if not action:
            raise KeyError(action_id)

        if action.status == "succeeded":
            return {
                "executed": False,
                "reason": "already_succeeded",
                "action": action.to_dict(),
                "evidence": [item.to_dict() for item in self.store.list_evidence(action.correlation_id)],
            }

        if action.risk == "red":
            return {"executed": False, "reason": "human_only", "action": action.to_dict()}
        if action.risk == "yellow" and not confirm:
            return {"executed": False, "reason": "approval_required", "action": action.to_dict()}
        if action.executor not in _AUTO_EXECUTORS:
            return {
                "executed": False,
                "reason": "external_executor_required",
                "action": action.to_dict(),
            }

        action = self.store.set_action_status(action_id, "running", increment_attempts=True)
        try:
            if action.executor == "readiness_check":
                assessment = self.readiness()
                terminal_status = "succeeded" if assessment["status"] == "ready" else "blocked"
                action = self.store.set_action_status(action_id, terminal_status)
                evidence, evidence_created = self.store.append_evidence(
                    action,
                    kind="readiness",
                    status=assessment["status"],
                    source="readiness_as_code",
                    payload=assessment,
                )
                return {
                    "executed": True,
                    "action": action.to_dict(),
                    "result": assessment,
                    "evidence": evidence.to_dict(),
                    "evidence_created": evidence_created,
                }
            raise OperationalOrchestratorError(f"Executor não implementado: {action.executor}")
        except Exception:
            self.store.set_action_status(action_id, "failed")
            raise

    def run_cycle(self, *, sha: str, branch: str = "main") -> dict[str, Any]:
        action, created = self.enqueue_readiness_check(sha=sha, branch=branch)
        execution = self.execute(action.action_id)
        return {
            "action_created": created,
            "execution": execution,
            "queue": self.store.summary(),
        }

    def status(self) -> dict[str, Any]:
        return {
            "service": "reqsys-operational-orchestrator",
            "readiness": self.readiness(),
            "queue": self.store.summary(),
            "policy": {
                "auto_executors": sorted(_AUTO_EXECUTORS),
                "yellow_requires_confirmation": True,
                "red_human_only": True,
                "evidence_append_only": True,
            },
        }
