#!/usr/bin/env python3
"""Gate SDD: exige especificação e rastreabilidade para mudança funcional."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

EXCLUDED_PREFIXES = (".sdd/", "docs/", "tests/", "backend/tests/", "artifacts/")
EXCLUDED_SUFFIXES = (".md", ".mdx")


def git_files(base_ref: str) -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"], text=True, capture_output=True, check=True)
    return sorted({p.strip().replace("\\", "/") for p in result.stdout.splitlines() if p.strip()})


def functional_files(files: list[str]) -> list[str]:
    return [p for p in files if not p.startswith(EXCLUDED_PREFIXES) and not p.endswith(EXCLUDED_SUFFIXES)]


def manifest_files(files: list[str]) -> list[str]:
    return [p for p in files if p.startswith(".sdd/specs/") and (p.endswith("/spec.json") or p.endswith(".spec.json"))]

def requirements_path(manifest: Path) -> Path:
    if manifest.name == "spec.json":
        return manifest.with_name("requirements.md")
    return manifest.with_name(manifest.name.removesuffix(".spec.json") + ".requirements.md")


def validate(root: Path, files: list[str], head_sha: str) -> tuple[bool, str]:
    functional = functional_files(files)
    if not functional:
        return True, "SDD não aplicável: nenhuma mudança funcional"
    manifests = manifest_files(files)
    if not manifests:
        return False, "SDD_SPEC_REQUIRED: mudança funcional sem especificação alterada"
    errors: list[str] = []
    for rel in manifests:
        path = root / rel
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{rel}: JSON inválido: {exc}")
            continue
        approvals = spec.get("approvals") or {}
        gate = spec.get("sdd_gate") or {}
        req = requirements_path(path)
        req_text = req.read_text(encoding="utf-8") if req.is_file() else ""
        if not str(spec.get("feature_name", "")).strip():
            errors.append(f"{rel}: feature_name ausente")
        if approvals.get("requirements") is not True:
            errors.append(f"{rel}: requirements não aprovado")
        lowered = req_text.lower()
        if "acceptance criteria" not in lowered and "critérios de aceite" not in lowered:
            errors.append(f"{rel}: critérios de aceite ausentes")
        tests = gate.get("tests") if isinstance(gate, dict) else None
        if not isinstance(tests, list) or not tests:
            errors.append(f"{rel}: sdd_gate.tests ausente")
        elif any(not (root / str(test)).is_file() for test in tests):
            errors.append(f"{rel}: teste mapeado inexistente")
    if errors:
        return False, "; ".join(errors)
    return True, f"SDD_OK head={head_sha} specs={len(manifests)} functional_files={len(functional)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida contrato SDD de mudanças funcionais")
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--head-sha", default="")
    args = parser.parse_args()
    root = Path.cwd()
    files = git_files(args.base_ref)
    head = args.head_sha or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    ok, detail = validate(root, files, head)
    print(detail)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
