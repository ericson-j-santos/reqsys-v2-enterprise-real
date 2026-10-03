#!/usr/bin/env python3
"""Fail closed when a BACEN integration surface appears without a declared contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "governance/bacen/integration-surfaces.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts/bacen/bacen-integration-surfaces.json"
ALLOWED_STATUS = {"active", "dormant"}


def load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("configuração BACEN deve ser um objeto YAML")
    return payload


def _iter_source_files(root: Path, scan_roots: list[str], extensions: set[str]):
    for rel_root in scan_roots:
        base = root / rel_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in extensions:
                yield path


def _detect_surface(path: Path, rel: str, detection: dict[str, Any]) -> bool:
    path_regex = str(detection.get("path_regex") or "")
    content_regex = str(detection.get("content_regex") or "")
    if path_regex and re.search(path_regex, rel):
        return True
    if not content_regex:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return re.search(content_regex, text) is not None


def validate(root: Path = ROOT, config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    policy = config.get("policy") or {}
    scan_roots = [str(item) for item in policy.get("scan_roots") or []]
    extensions = {str(item).lower() for item in policy.get("executable_extensions") or []}
    activation_requires = [str(item) for item in policy.get("activation_requires") or []]
    surfaces = config.get("surfaces") or []

    errors: list[str] = []
    warnings: list[str] = []
    detections: dict[str, list[str]] = {}
    seen_ids: set[str] = set()

    if not scan_roots:
        errors.append("policy.scan_roots vazio")
    if not extensions:
        errors.append("policy.executable_extensions vazio")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("surfaces vazio")
        surfaces = []

    source_files = list(_iter_source_files(root, scan_roots, extensions))
    digest = hashlib.sha256()
    digest.update(config_path.read_bytes())
    for path in source_files:
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(path.read_bytes())

    for surface in surfaces:
        if not isinstance(surface, dict):
            errors.append("surface inválida: esperado objeto")
            continue
        surface_id = str(surface.get("id") or "").strip()
        status = str(surface.get("status") or "").strip()
        if not surface_id:
            errors.append("surface sem id")
            continue
        if surface_id in seen_ids:
            errors.append(f"surface duplicada: {surface_id}")
            continue
        seen_ids.add(surface_id)
        if status not in ALLOWED_STATUS:
            errors.append(f"{surface_id}: status inválido {status!r}")
            continue

        detection = surface.get("detection") or {}
        detected = []
        for path in source_files:
            rel = path.relative_to(root).as_posix()
            if _detect_surface(path, rel, detection):
                detected.append(rel)
        detections[surface_id] = sorted(set(detected))

        consumer_paths = [str(item) for item in surface.get("consumer_paths") or []]
        contract_tests = [str(item) for item in surface.get("contract_tests") or []]

        if status == "dormant":
            if detected:
                errors.append(
                    f"{surface_id}: consumidor detectado enquanto surface=dormant: "
                    + ", ".join(sorted(set(detected)))
                )
            continue

        for field in activation_requires:
            value = surface.get(field)
            if value in (None, "", []):
                errors.append(f"{surface_id}: surface ativa sem {field}")

        missing_paths = [rel for rel in consumer_paths + contract_tests if not (root / rel).is_file()]
        for rel in missing_paths:
            errors.append(f"{surface_id}: caminho declarado ausente: {rel}")

        required_markers = [str(item) for item in surface.get("required_consumer_markers") or []]
        consumer_text = ""
        for rel in consumer_paths:
            path = root / rel
            if path.is_file():
                consumer_text += "\n" + path.read_text(encoding="utf-8", errors="replace")
        for marker in required_markers:
            if marker not in consumer_text:
                errors.append(f"{surface_id}: marcador contratual ausente: {marker}")

        if not detected:
            warnings.append(f"{surface_id}: surface ativa sem detecção heurística; revisar detection")

    result = {
        "schema_version": "1.0.0",
        "gate": "BACEN Integration Surface Compatibility",
        "result": "valid" if not errors else "invalid",
        "config": config_path.relative_to(root).as_posix() if config_path.is_relative_to(root) else str(config_path),
        "scanned_files": len(source_files),
        "input_sha256": digest.hexdigest(),
        "surfaces": {
            str(surface.get("id")): {
                "status": str(surface.get("status")),
                "detections": detections.get(str(surface.get("id")), []),
            }
            for surface in surfaces
            if isinstance(surface, dict) and surface.get("id")
        },
        "errors": errors,
        "warnings": warnings,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    root = args.root.resolve()
    config_path = (args.config or (root / "governance/bacen/integration-surfaces.yaml")).resolve()
    result = validate(root=root, config_path=config_path)

    output = args.output
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
