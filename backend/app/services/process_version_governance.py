"""Promocao e restauracao governada de versoes de processos.

A operacao nunca altera uma revisao existente. Uma promocao cria uma nova
revisao imutavel, atualiza um ponteiro operacional e registra evidencia de
auditoria com controle de concorrencia otimista.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.process_artifact_repository import (
    ProcessArtifactComparisonError,
    ProcessArtifactNotFoundError,
    VersionedProcessArtifactRepository,
)


class ProcessPromotionConflictError(RuntimeError):
    """O estado ativo mudou desde a leitura do solicitante."""


class ProcessPromotionValidationError(ValueError):
    """Solicitacao de promocao invalida."""


@dataclass(frozen=True)
class ProcessPromotionEvent:
    event_id: str
    process_id: str
    source_revision: str
    promoted_revision: str
    target_version: str
    previous_active_revision: str | None
    actor: str
    reason: str
    correlation_id: str
    promoted_at: str


class ProcessVersionGovernanceService:
    """Coordena promocao imutavel, ponteiro ativo e trilha de auditoria."""

    def __init__(self, repository: VersionedProcessArtifactRepository | None = None) -> None:
        self.repository = repository or VersionedProcessArtifactRepository()

    def promote(
        self,
        process_id: str,
        source_revision: str,
        target_version: str,
        actor: str,
        reason: str,
        correlation_id: str,
        expected_current_revision: str | None = None,
    ) -> dict[str, Any]:
        process_id = self._required(process_id, "process_id", 120)
        source_revision = self._required(source_revision, "source_revision", 200)
        target_version = self._required(target_version, "target_version", 40)
        actor = self._required(actor, "actor", 160)
        reason = self._required(reason, "reason", 500)
        correlation_id = self._required(correlation_id, "correlation_id", 160)

        source = self.repository.get_version(process_id, source_revision)
        definition = source.get("definition")
        if not isinstance(definition, dict):
            raise ProcessArtifactComparisonError(
                "revisao sem snapshot estrutural; gere novamente antes de promover"
            )

        current = self.get_active(process_id, required=False)
        current_revision = current.get("active_revision") if current else None
        if expected_current_revision is not None and expected_current_revision != current_revision:
            raise ProcessPromotionConflictError(
                f"revisao ativa divergente: esperada={expected_current_revision}, atual={current_revision}"
            )

        promoted_definition = dict(definition)
        promoted_definition["version"] = target_version
        artifact = {
            "process_id": process_id,
            "process_name": source.get("process_name") or promoted_definition.get("name"),
            "process_version": target_version,
            "content_hash": source["content_hash"],
            "generated_at": datetime.now(UTC).isoformat(),
            "correlation_id": correlation_id,
            "metrics": source.get("metrics", {}),
            "definition": promoted_definition,
            "formats": source.get("formats", {}),
        }
        persisted = self.repository.save(artifact)
        promoted_at = datetime.now(UTC).isoformat()
        event_seed = "|".join(
            [process_id, source_revision, persisted.revision, actor, correlation_id, promoted_at]
        )
        event_id = hashlib.sha256(event_seed.encode("utf-8")).hexdigest()[:24]
        event = ProcessPromotionEvent(
            event_id=event_id,
            process_id=process_id,
            source_revision=source_revision,
            promoted_revision=persisted.revision,
            target_version=target_version,
            previous_active_revision=current_revision,
            actor=actor,
            reason=reason,
            correlation_id=correlation_id,
            promoted_at=promoted_at,
        )
        self._persist_event(event)
        self._write_active_pointer(event)
        return {
            "schema_version": "1.0.0",
            "status": "promoted",
            "event": asdict(event),
            "artifact": asdict(persisted),
        }

    def get_active(self, process_id: str, *, required: bool = True) -> dict[str, Any] | None:
        safe_process_id = self._safe_segment(process_id)
        pointer = self.repository.root_dir / safe_process_id / "governance" / "active.json"
        if not pointer.exists():
            if required:
                raise ProcessArtifactNotFoundError(f"processo sem revisao ativa: {process_id}")
            return None
        return json.loads(pointer.read_text(encoding="utf-8"))

    def list_events(self, process_id: str) -> list[dict[str, Any]]:
        safe_process_id = self._safe_segment(process_id)
        events_dir = self.repository.root_dir / safe_process_id / "governance" / "events"
        if not events_dir.exists():
            return []
        events = [json.loads(path.read_text(encoding="utf-8")) for path in events_dir.glob("*.json")]
        return sorted(events, key=lambda item: str(item.get("promoted_at", "")), reverse=True)

    def _persist_event(self, event: ProcessPromotionEvent) -> None:
        safe_process_id = self._safe_segment(event.process_id)
        event_file = (
            self.repository.root_dir
            / safe_process_id
            / "governance"
            / "events"
            / f"{event.promoted_at.replace(':', '').replace('+', '_')}_{event.event_id}.json"
        )
        self._write_atomic(event_file, json.dumps(asdict(event), ensure_ascii=False, indent=2, sort_keys=True))

    def _write_active_pointer(self, event: ProcessPromotionEvent) -> None:
        safe_process_id = self._safe_segment(event.process_id)
        pointer = self.repository.root_dir / safe_process_id / "governance" / "active.json"
        payload = {
            "schema_version": "1.0.0",
            "process_id": event.process_id,
            "active_revision": event.promoted_revision,
            "source_revision": event.source_revision,
            "target_version": event.target_version,
            "activated_at": event.promoted_at,
            "activated_by": event.actor,
            "reason": event.reason,
            "correlation_id": event.correlation_id,
            "event_id": event.event_id,
        }
        self._write_atomic(pointer, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    @staticmethod
    def _required(value: str, field: str, max_length: int) -> str:
        normalized = value.strip()
        if not normalized:
            raise ProcessPromotionValidationError(f"{field} e obrigatorio")
        if len(normalized) > max_length:
            raise ProcessPromotionValidationError(f"{field} excede {max_length} caracteres")
        return normalized

    @staticmethod
    def _safe_segment(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value.strip())
        if not sanitized or sanitized in {".", ".."}:
            raise ProcessPromotionValidationError("identificador de processo invalido")
        return sanitized[:160]

    @staticmethod
    def _write_atomic(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)
