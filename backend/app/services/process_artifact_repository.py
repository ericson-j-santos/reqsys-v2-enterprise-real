"""Persistencia versionada e auditavel de artefatos de processo."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ProcessArtifactNotFoundError(LookupError):
    """Artefato ou revisao de processo nao encontrado."""


class ProcessArtifactComparisonError(ValueError):
    """Revisoes sem snapshot estrutural comparavel."""


@dataclass(frozen=True)
class PersistedProcessArtifact:
    process_id: str
    version: str
    revision: str
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
        metadata = {
            "schema_version": "1.1.0",
            "revision": revision,
            "process_id": artifact["process_id"],
            "process_name": artifact.get("process_name"),
            "process_version": artifact["process_version"],
            "content_hash": content_hash,
            "generated_at": generated_at,
            "correlation_id": artifact.get("correlation_id"),
            "metrics": artifact.get("metrics", {}),
            "definition": artifact.get("definition"),
        }

        self._write_atomic(mermaid_file, str(formats.get("mermaid", "")))
        self._write_atomic(bpmn_file, str(formats.get("bpmn_2_0_xml", "")))
        self._write_atomic(metadata_file, json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
        self._update_manifest(process_id, revision, metadata_file)
        return PersistedProcessArtifact(
            process_id=str(artifact["process_id"]),
            version=str(artifact["process_version"]),
            revision=revision,
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

    def get_version(self, process_id: str, revision: str) -> dict[str, Any]:
        safe_process_id = self._safe_segment(process_id)
        safe_revision = self._safe_segment(revision)
        revision_dir = self.root_dir / safe_process_id / safe_revision
        metadata_file = revision_dir / "metadata.json"
        if not metadata_file.exists():
            raise ProcessArtifactNotFoundError(f"revisao nao encontrada: {revision}")
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        metadata["formats"] = {
            "mermaid": self._read_optional(revision_dir / "diagram.mmd"),
            "bpmn_2_0_xml": self._read_optional(revision_dir / "process.bpmn"),
        }
        metadata["persistence"] = {
            "directory": str(revision_dir),
            "metadata_file": str(metadata_file),
        }
        return metadata

    def compare_versions(self, process_id: str, base_revision: str, target_revision: str) -> dict[str, Any]:
        base = self.get_version(process_id, base_revision)
        target = self.get_version(process_id, target_revision)
        base_definition = base.get("definition")
        target_definition = target.get("definition")
        if not isinstance(base_definition, dict) or not isinstance(target_definition, dict):
            raise ProcessArtifactComparisonError("revisao sem snapshot estrutural; gere novamente para comparar")

        base_nodes = {str(item["id"]): item for item in base_definition.get("nodes", [])}
        target_nodes = {str(item["id"]): item for item in target_definition.get("nodes", [])}
        base_edges = {self._edge_key(item): item for item in base_definition.get("edges", [])}
        target_edges = {self._edge_key(item): item for item in target_definition.get("edges", [])}

        common_nodes = sorted(base_nodes.keys() & target_nodes.keys())
        changed_nodes = [
            {"id": node_id, "before": base_nodes[node_id], "after": target_nodes[node_id]}
            for node_id in common_nodes
            if base_nodes[node_id] != target_nodes[node_id]
        ]
        common_edges = sorted(base_edges.keys() & target_edges.keys())
        changed_edges = [
            {"key": key, "before": base_edges[key], "after": target_edges[key]}
            for key in common_edges
            if base_edges[key] != target_edges[key]
        ]
        diff = {
            "nodes": {
                "added": [target_nodes[key] for key in sorted(target_nodes.keys() - base_nodes.keys())],
                "removed": [base_nodes[key] for key in sorted(base_nodes.keys() - target_nodes.keys())],
                "changed": changed_nodes,
            },
            "edges": {
                "added": [target_edges[key] for key in sorted(target_edges.keys() - base_edges.keys())],
                "removed": [base_edges[key] for key in sorted(base_edges.keys() - target_edges.keys())],
                "changed": changed_edges,
            },
            "process": {
                "name_changed": base_definition.get("name") != target_definition.get("name"),
                "before_name": base_definition.get("name"),
                "after_name": target_definition.get("name"),
                "before_version": base_definition.get("version"),
                "after_version": target_definition.get("version"),
            },
        }
        total_changes = sum(len(group[key]) for group in (diff["nodes"], diff["edges"]) for key in ("added", "removed", "changed"))
        total_changes += int(diff["process"]["name_changed"])
        return {
            "schema_version": "1.0.0",
            "process_id": process_id,
            "base_revision": base_revision,
            "target_revision": target_revision,
            "has_changes": total_changes > 0,
            "total_changes": total_changes,
            "diff": diff,
        }

    def _update_manifest(self, process_id: str, revision: str, metadata_file: Path) -> None:
        manifest_path = self.root_dir / process_id / "manifest.json"
        manifest = self._load_manifest(process_id)
        versions = [item for item in manifest.get("versions", []) if item.get("revision") != revision]
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        versions.append({
            "revision": revision,
            "process_id": metadata.get("process_id"),
            "process_name": metadata.get("process_name"),
            "process_version": metadata.get("process_version"),
            "content_hash": metadata.get("content_hash"),
            "generated_at": metadata.get("generated_at"),
            "correlation_id": metadata.get("correlation_id"),
            "metrics": metadata.get("metrics", {}),
            "metadata_file": str(metadata_file),
        })
        versions.sort(key=lambda item: str(item.get("generated_at", "")), reverse=True)
        self._write_atomic(manifest_path, json.dumps({
            "schema_version": "1.1.0",
            "process_id": process_id,
            "latest_revision": revision,
            "updated_at": datetime.now(UTC).isoformat(),
            "versions": versions,
        }, ensure_ascii=False, indent=2, sort_keys=True))

    def _load_manifest(self, process_id: str) -> dict[str, Any]:
        manifest_path = self.root_dir / process_id / "manifest.json"
        if not manifest_path.exists():
            return {"schema_version": "1.1.0", "process_id": process_id, "versions": []}
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    @staticmethod
    def _edge_key(edge: dict[str, Any]) -> str:
        return f"{edge.get('source', '')}->{edge.get('target', '')}"

    @staticmethod
    def _read_optional(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

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
