#!/usr/bin/env python3
"""Mede cobertura das linhas Python alteradas no backend do ReqSys.

Modo padrão: report-only. O script gera evidência mesmo quando a cobertura
diferencial fica abaixo do mínimo informado. Use --enforce explicitamente para
retornar código 1 nesse caso.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COVERAGE = ROOT / "artifacts" / "quality-fabric" / "runtime" / "backend-coverage.json"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "quality-fabric" / "runtime"
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class DifferentialCoverageError(ValueError):
    """Entrada inválida ou evidência de cobertura inconsistente."""


def _safe_repo_path(path: Path, *, must_exist: bool = False) -> Path:
    candidate = path if path.is_absolute() else ROOT / path
    resolved = candidate.resolve()
    root = ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise DifferentialCoverageError(f"Caminho fora do repositório: {path}")
    if must_exist and not resolved.exists():
        raise DifferentialCoverageError(f"Arquivo não encontrado: {path}")
    return resolved


def parse_changed_lines(diff_text: str) -> dict[str, set[int]]:
    """Extrai linhas do lado head a partir de `git diff --unified=0`."""
    changed: dict[str, set[int]] = {}
    current_file: str | None = None

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("+++ "):
            value = raw_line[4:].strip()
            if value == "/dev/null":
                current_file = None
                continue
            current_file = value[2:] if value.startswith("b/") else value
            current_file = current_file.replace("\\", "/")
            changed.setdefault(current_file, set())
            continue

        if current_file is None:
            continue

        match = _HUNK_RE.match(raw_line)
        if not match:
            continue

        start = int(match.group(1))
        count = int(match.group(2) or "1")
        if count <= 0:
            continue
        changed[current_file].update(range(start, start + count))

    return changed


def git_changed_lines(base_sha: str, head_sha: str) -> dict[str, set[int]]:
    proc = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            "--no-ext-diff",
            base_sha,
            head_sha,
            "--",
            "backend/app",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise DifferentialCoverageError(f"Falha ao calcular diff: {detail}")
    return parse_changed_lines(proc.stdout)


def load_coverage(path: Path) -> dict[str, Any]:
    resolved = _safe_repo_path(path, must_exist=True)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        raise DifferentialCoverageError("coverage.json inválido: campo 'files' ausente.")
    return payload


def normalize_coverage_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("backend/"):
        return normalized
    if normalized.startswith("app/"):
        return f"backend/{normalized}"
    candidate = Path(normalized)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(ROOT.resolve())
            return relative.as_posix()
        except ValueError:
            return normalized
    return normalized


def evaluate_differential_coverage(
    coverage: dict[str, Any],
    changed_lines: dict[str, set[int]],
    *,
    minimum: float,
) -> dict[str, Any]:
    coverage_files: dict[str, dict[str, Any]] = {
        normalize_coverage_path(path): data
        for path, data in coverage["files"].items()
        if isinstance(data, dict)
    }

    files: list[dict[str, Any]] = []
    total_executable = 0
    total_covered = 0
    total_missing = 0

    for path in sorted(changed_lines):
        if not path.startswith("backend/app/"):
            continue

        changed = set(changed_lines[path])
        data = coverage_files.get(path, {})
        executed = {int(line) for line in data.get("executed_lines", [])}
        missing = {int(line) for line in data.get("missing_lines", [])}
        executable = executed | missing

        executable_changed = changed & executable
        covered_changed = executable_changed & executed
        missing_changed = executable_changed & missing

        executable_count = len(executable_changed)
        covered_count = len(covered_changed)
        missing_count = len(missing_changed)
        percent = (
            round((covered_count / executable_count) * 100.0, 2)
            if executable_count
            else None
        )

        total_executable += executable_count
        total_covered += covered_count
        total_missing += missing_count

        files.append(
            {
                "path": path,
                "changed_lines": sorted(changed),
                "executable_changed_lines": sorted(executable_changed),
                "covered_changed_lines": sorted(covered_changed),
                "missing_changed_lines": sorted(missing_changed),
                "coverage_percent": percent,
            }
        )

    overall_percent = (
        round((total_covered / total_executable) * 100.0, 2)
        if total_executable
        else None
    )

    if overall_percent is None:
        status = "not_applicable"
    elif overall_percent >= minimum:
        status = "pass"
    else:
        status = "warning"

    return {
        "schema_version": "1.0",
        "mode": "report-only",
        "minimum_percent": minimum,
        "status": status,
        "coverage_percent": overall_percent,
        "executable_changed_lines": total_executable,
        "covered_changed_lines": total_covered,
        "missing_changed_lines": total_missing,
        "files": files,
    }


def render_markdown(evidence: dict[str, Any]) -> str:
    percent = evidence["coverage_percent"]
    percent_text = "n/a" if percent is None else f"{percent:.2f}%"
    lines = [
        "# ReqSys Quality Fabric — Cobertura diferencial",
        "",
        f"- Status: **{evidence['status']}**",
        f"- Cobertura das linhas executáveis alteradas: **{percent_text}**",
        f"- Referência informativa: **{evidence['minimum_percent']:.2f}%**",
        f"- Linhas executáveis alteradas: {evidence['executable_changed_lines']}",
        f"- Cobertas: {evidence['covered_changed_lines']}",
        f"- Não cobertas: {evidence['missing_changed_lines']}",
        "",
        "| Arquivo | Executáveis alteradas | Cobertas | Não cobertas | Cobertura |",
        "|---|---:|---:|---:|---:|",
    ]
    for item in evidence["files"]:
        file_percent = item["coverage_percent"]
        file_percent_text = "n/a" if file_percent is None else f"{file_percent:.2f}%"
        lines.append(
            f"| `{item['path']}` | {len(item['executable_changed_lines'])} | "
            f"{len(item['covered_changed_lines'])} | {len(item['missing_changed_lines'])} | "
            f"{file_percent_text} |"
        )
    lines.extend(
        [
            "",
            "> Report-only: resultado abaixo da referência não bloqueia merge neste incremento.",
            "",
        ]
    )
    return "\n".join(lines)


def write_evidence(evidence: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    resolved = _safe_repo_path(output_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    json_path = resolved / "differential-coverage.json"
    markdown_path = resolved / "differential-coverage.md"
    json_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(evidence), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ReqSys Quality Fabric — cobertura diferencial")
    parser.add_argument("--coverage-json", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--minimum", type=float, default=85.0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0.0 <= args.minimum <= 100.0:
        raise DifferentialCoverageError("--minimum deve estar entre 0 e 100.")

    coverage = load_coverage(args.coverage_json)
    changed = git_changed_lines(args.base_sha, args.head_sha)
    evidence = evaluate_differential_coverage(coverage, changed, minimum=args.minimum)
    write_evidence(evidence, args.output_dir)
    print(render_markdown(evidence))

    if args.enforce and evidence["status"] == "warning":
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DifferentialCoverageError, OSError, json.JSONDecodeError) as exc:
        print(f"quality-fabric-differential-coverage: erro: {exc}", file=sys.stderr)
        raise SystemExit(2)
