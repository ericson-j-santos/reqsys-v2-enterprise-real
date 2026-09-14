#!/usr/bin/env python3
"""Gate de prontidão antes da abertura de Pull Request.

Executa apenas verificações determinísticas que podem ser antecipadas para a branch,
registra evidência vinculada ao HEAD e falha fechado quando a branch está desatualizada
ou um check obrigatório falha.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str
    duration_seconds: float


@dataclass(frozen=True)
class ReadinessEvidence:
    schema_version: str
    status: str
    correlation_id: str
    base_ref: str
    base_sha: str
    head_sha: str
    behind_by: int
    changed_files: list[str]
    profiles: list[str]
    checks: list[dict[str, object]]
    blockers: list[str]
    warnings: list[str]


def run(args: Iterable[str], *, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_stdout(*args: str) -> str:
    completed = run(["git", *args])
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falhou: {completed.stderr.strip()}")
    return completed.stdout.strip()


def detect_profiles(files: list[str]) -> list[str]:
    profiles: set[str] = set()
    if files and all(path.startswith("docs/") or path.endswith((".md", ".mdx")) for path in files):
        profiles.add("docs_only")
    if any(path.startswith((".github/workflows/", "scripts/", "tests/", "docs/runbooks/")) for path in files):
        profiles.add("operational")
    if any(path.startswith("backend/") for path in files):
        profiles.add("backend")
    if any(path.startswith("frontend/") for path in files):
        profiles.add("frontend")
    if not profiles:
        profiles.add("general")
    return sorted(profiles)


def changed_files(base_ref: str) -> list[str]:
    output = git_stdout("diff", "--name-only", f"origin/{base_ref}...HEAD")
    return sorted({line.strip() for line in output.splitlines() if line.strip()})


def candidate_pytests(files: list[str], root: Path) -> list[str]:
    candidates: set[str] = set()
    for path in files:
        if path.endswith(".py") and (path.startswith("tests/") or path.startswith("backend/tests/")):
            if (root / path).is_file():
                candidates.add(path)
        if path.startswith("scripts/") and path.endswith(".py"):
            stem = Path(path).stem
            for candidate in (f"tests/test_{stem}.py", f"backend/tests/test_{stem}.py"):
                if (root / candidate).is_file():
                    candidates.add(candidate)
    return sorted(candidates)


def _timed_check(name: str, command: list[str], *, cwd: Path | None = None) -> CheckResult:
    started = time.monotonic()
    completed = run(command, cwd=cwd)
    duration = round(time.monotonic() - started, 3)
    if completed.returncode == 0:
        detail = (completed.stdout.strip() or "ok")[-1200:]
        return CheckResult(name, "passed", detail, duration)
    detail = (completed.stderr.strip() or completed.stdout.strip() or f"exit={completed.returncode}")[-2000:]
    return CheckResult(name, "failed", detail, duration)


def targeted_pytest_checks(targeted: list[str], root: Path) -> list[CheckResult]:
    """Executa testes direcionados no diretório que fornece seu import root.

    Testes em ``backend/tests`` precisam rodar com ``backend`` como cwd para que
    imports ``app.*`` resolvam exatamente como nos workflows oficiais do backend.
    Testes de raiz continuam executando no root do repositório. Os grupos são
    separados para suportar um mesmo incremento que altere gate e backend.
    """
    results: list[CheckResult] = []
    root_tests = [path for path in targeted if path.startswith("tests/")]
    backend_tests = [path for path in targeted if path.startswith("backend/tests/")]
    unknown = [path for path in targeted if path not in root_tests and path not in backend_tests]

    if root_tests:
        results.append(
            _timed_check(
                "targeted:pytest:root",
                [sys.executable, "-m", "pytest", *root_tests, "-q"],
                cwd=root,
            )
        )
    if backend_tests:
        relative = [str(Path(path).relative_to("backend")) for path in backend_tests]
        results.append(
            _timed_check(
                "targeted:pytest:backend",
                [sys.executable, "-m", "pytest", *relative, "-q"],
                cwd=root / "backend",
            )
        )
    if unknown:
        results.append(
            CheckResult(
                "targeted:pytest:unknown",
                "failed",
                f"caminhos de teste sem import root conhecido: {', '.join(unknown)}",
                0.0,
            )
        )
    return results


def validate_structured_files(files: list[str], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for rel in files:
        path = root / rel
        if not path.is_file():
            continue
        if rel.endswith(".json"):
            started = time.monotonic()
            try:
                json.loads(path.read_text(encoding="utf-8"))
                results.append(CheckResult(f"json:{rel}", "passed", "JSON válido", round(time.monotonic() - started, 3)))
            except Exception as exc:
                results.append(CheckResult(f"json:{rel}", "failed", str(exc), round(time.monotonic() - started, 3)))
        elif rel.endswith((".yml", ".yaml")):
            started = time.monotonic()
            try:
                import yaml  # type: ignore

                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
                if rel.startswith(".github/workflows/"):
                    if not isinstance(payload, dict) or "jobs" not in payload:
                        raise ValueError("workflow sem objeto jobs")
                    if "name" not in payload:
                        raise ValueError("workflow sem name")
                    # PyYAML 1.1 pode converter a chave 'on' para True.
                    if "on" not in payload and True not in payload:
                        raise ValueError("workflow sem gatilho on")
                results.append(CheckResult(f"yaml:{rel}", "passed", "YAML válido", round(time.monotonic() - started, 3)))
            except Exception as exc:
                results.append(CheckResult(f"yaml:{rel}", "failed", str(exc), round(time.monotonic() - started, 3)))
    return results


def validate_python(files: list[str], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for rel in files:
        if not rel.endswith(".py") or not (root / rel).is_file():
            continue
        results.append(_timed_check(f"py_compile:{rel}", [sys.executable, "-m", "py_compile", rel], cwd=root))
    return results


def operational_fast_checks(root: Path) -> list[CheckResult]:
    scripts = [
        "scripts/pr_ci_watch.py",
        "scripts/workflow_command_center.py",
        "scripts/auto_rerun_governed.py",
        "scripts/workflow_inventory_audit.py",
        "scripts/workflow_inventory_decision_gate.py",
    ]
    tests = [
        "tests/test_pr_ci_watch.py",
        "tests/test_workflow_command_center.py",
        "tests/test_auto_rerun_governed.py",
        "tests/test_workflow_inventory_audit.py",
        "tests/test_workflow_inventory_decision_gate.py",
    ]
    results: list[CheckResult] = []
    existing_scripts = [item for item in scripts if (root / item).is_file()]
    if existing_scripts:
        results.append(_timed_check("operational:py_compile", [sys.executable, "-m", "py_compile", *existing_scripts], cwd=root))
    existing_tests = [item for item in tests if (root / item).is_file()]
    if existing_tests:
        results.append(_timed_check("operational:pytest", [sys.executable, "-m", "pytest", *existing_tests, "-q"], cwd=root))
    return results


def frontend_build(root: Path) -> CheckResult:
    frontend = root / "frontend"
    if not (frontend / "package.json").is_file():
        return CheckResult("frontend:build", "failed", "frontend/package.json ausente", 0.0)
    install = _timed_check("frontend:npm-ci", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=frontend)
    if install.status != "passed":
        return install
    return _timed_check("frontend:build", ["npm", "run", "build"], cwd=frontend)


def self_test_negative() -> bool:
    with tempfile.TemporaryDirectory(prefix="reqsys-pre-pr-negative-") as tmp:
        root = Path(tmp)
        bad = root / "invalid.json"
        bad.write_text("{invalid", encoding="utf-8")
        results = validate_structured_files(["invalid.json"], root)
        return len(results) == 1 and results[0].status == "failed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida READY_FOR_PR antes de abrir a Pull Request.")
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--expected-head-sha", default=os.getenv("GITHUB_SHA", ""))
    parser.add_argument("--correlation-id", default=os.getenv("CORRELATION_ID", "pre-pr-local"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/pre-pr-readiness/pre-pr-readiness.json"))
    parser.add_argument("--self-test-negative", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test_negative:
        ok = self_test_negative()
        print(json.dumps({"self_test_negative": ok}))
        return 0 if ok else 1

    root = Path.cwd()
    blockers: list[str] = []
    warnings: list[str] = []
    checks: list[CheckResult] = []

    fetch = run(["git", "fetch", "origin", args.base_ref, "--prune"], cwd=root)
    if fetch.returncode != 0:
        print(fetch.stderr, file=sys.stderr)
        return 2

    head_sha = git_stdout("rev-parse", "HEAD")
    base_sha = git_stdout("rev-parse", f"origin/{args.base_ref}")
    behind_by = int(git_stdout("rev-list", "--count", f"HEAD..origin/{args.base_ref}") or "0")
    files = changed_files(args.base_ref)
    profiles = detect_profiles(files)

    if args.expected_head_sha and head_sha != args.expected_head_sha:
        blockers.append(f"HEAD divergente da execução: esperado {args.expected_head_sha}, obtido {head_sha}")
    if behind_by > 0:
        blockers.append(f"branch está {behind_by} commit(s) atrás de {args.base_ref}; atualizar antes da PR")
    if not files:
        blockers.append("nenhuma alteração detectada em relação à base")

    checks.extend(validate_python(files, root))
    checks.extend(validate_structured_files(files, root))

    targeted = candidate_pytests(files, root)
    if targeted:
        checks.extend(targeted_pytest_checks(targeted, root))

    if "operational" in profiles:
        checks.extend(operational_fast_checks(root))

    if "frontend" in profiles:
        checks.append(frontend_build(root))

    if "backend" in profiles:
        warnings.append("backend alterado: este gate v1 antecipa sintaxe/testes diretamente relacionados; suíte integrada permanece no CI da PR")

    failed = [item for item in checks if item.status != "passed"]
    blockers.extend(f"{item.name}: {item.detail}" for item in failed)
    status = "passed" if not blockers else "blocked"

    evidence = ReadinessEvidence(
        schema_version="1.0.0",
        status=status,
        correlation_id=args.correlation_id,
        base_ref=args.base_ref,
        base_sha=base_sha,
        head_sha=head_sha,
        behind_by=behind_by,
        changed_files=files,
        profiles=profiles,
        checks=[asdict(item) for item in checks],
        blockers=blockers,
        warnings=warnings,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(evidence), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asdict(evidence), ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
