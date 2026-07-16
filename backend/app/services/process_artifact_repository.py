"""Persistencia versionada e auditavel de artefatos de processo.

Usa somente a biblioteca padrao, escrita atomica e manifesto por processo.
O diretorio pode ser configurado por ``REQSYS_DIAGRAM_ARTIFACTS_DIR``.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PersistedProcessArtifact:
    process_id: str
    version: str
    content_hash: str
    generated_at: str
    directory: str
    mermaid_file: str
    bpmn_file: str
    metadata_file: str


class VersionedProcessArtifactRepository:
    """Repositorio filesystem com versoes imutaveis identificadas por hash."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        configured = root_dir or os.getenv("REQSYS_DIAGRAM_ARTIFACTS_DIR", ".diagram-artifacts")
        self.root_dir = Path(configured)

    def save(self, artifact: dict[str, Any]) -> PersistedProcessArtifact:
        process_id = self._safe_segment(str(artifact["process_id"]))
        version = self._safe_segment(str(artifact["process_version"]))
        content_hash = str(artifact["content_hash"])
        generated_at = str(artifact.get("generated_at") or datetime.now(UTC).isoformat())
        revision = f"{version}-{content_hash[:12]}"
        revision_dir = self.root_dir / process_id / revision
        revision_dir.mkdir(parents=True, exist_ok=True)

        mermaid_file = revision_dir / "diagram.mmd"
        bpmn_file = revision_dir / "process.bpmn"
        metadata_file = revision_dir / "metadata.json"
        formats = artifact.get("formats", {})

        self._write_atomic(mermaid_file, str(formats.get("mermaid", "")))
        self._write_atomic(bpmn_file, str(formats.get("bpmn_2_0_xml", "")))
        self._write_atomic(
            metadata_file,
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "process_id": artifact["process_id"],
                    "process_name": artifact.get("process_name"),
                    "process_version": artifact["process_version"],
                    "content_hash": content_hash,
                    "generated_at": generated_at,
                    "correlation_id": artifact.get("correlation_id"),
                    "metrics": artifact.get("metrics", {}),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
        )
        self._update_manifest(process_id, revision, metadata_file)
        return PersistedProcessArtifact(
            process_id=str(artifact["process_id"]),
            version=str(artifact["process_version"]),
            content_hash=content_hash,
            generated_at=generated_at,
            directory=str(revision_dir),
            mermaid_file=str(mermaid_file),
            bpmn_file=str(bpmn_file),
            metadata_file=str(metadata_file),
        )

    def list_versions(self, process_id: str) -> list[dict[str, Any]]:
        manifest = self._load_manifest(self._safe_segment(process_id))
        return list(manifest.get("versions", []))

    def _update_manifest(self, process_id: str, revision: str, metadata_file: Path) -> None:
        manifest_path = self.root_dir / process_id / "manifest.json"
        manifest = self._load_manifest(process_id)
        versions = [item for item in manifest.get("versions", []) if item.get("revision") != revision]
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        versions.append({"revision": revision, **metadata, "metadata_file": str(metadata_file)})
        versions.sort(key=lambda item: str(item.get("generated_at", "")), reverse=True)
        self._write_atomic(
            manifest_path,
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "process_id": process_id,
                    "latest_revision": revision,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "versions": versions,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
        )

    def _load_manifest(self, process_id: str) -> dict[str, Any]:
        manifest_path = self.root_dir / process_id / "manifest.json"
        if not manifest_path.exists():
            return {"schema_version": "1.0.0", "process_id": process_id, "versions": []}
        return json.loads(manifest_path.read_text(encoding="utf-8"))

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

    @staticmethod
    def _safe_segment(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", value.strip())
        if not sanitized or sanitized in {".", ".."}:
            raise ValueError("identificador de artefato invalido")
        return sanitized[:160]
