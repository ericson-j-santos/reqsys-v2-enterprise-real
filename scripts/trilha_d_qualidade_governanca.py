#!/usr/bin/env python3
"""Trilha D — Qualidade e Governança."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CONTRACTS = ROOT / "docs" / "contracts"
DEFAULT_OUTPUT = ROOT / "artifacts" / "trilha-d-qualidade-governanca"

DIMENSIONS = ("tests", "coverage", "mutation", "contract", "schema", "ci-watch")
STATE_RANK = {"passed": 0, "warning": 1, "failed": 2, "skipped": 3}


@dataclass
class DimensionResult:
    dimension: str
    status: str
    score: float
    duration_seconds: float
    summary: str
    details: dict[str, Any]
    blockers: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        command,
        cwd=cwd or ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def backend_test_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "sqlite:///./reqsys_trilha_d.db",
        "JWT_SECRET_KEY": "ci-secret-key-for-testing-only",
        "JWT_SECRET": "ci-secret-key-for-testing-only-minimum-32-characters",
        "JWT_ISSUER": "reqsys-ci",
        "JWT_AUDIENCE": "reqsys-ci-tests",
        "JWT_EXP_MINUTES": "60",
        "ALLOW_DEMO_LOGIN": "true",
        "APP_ENV": "test",
        "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000000",
        "AZURE_CLIENT_ID": "11111111-1111-1111-1111-111111111111",
        "AZURE_AUTHORITY": "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000",
        "REDMINE_URL": "https://placeholder.example.com",
        "REDMINE_API_KEY": "placeholder",
        "ENABLE_GITHUB_REDMINE_IMPORT": "false",
        "SSRS_BASE_URL": "",
        "GITHUB_WEBHOOK_SECRET": "",
        "GITLAB_WEBHOOK_TOKEN": "",
    }


def parse_pytest_summary(output: str) -> dict[str, int]:
    return {
        "passed": int(re.search(r"(\d+) passed", output).group(1)) if re.search(r"(\d+) passed", output) else 0,
        "failed": int(re.search(r"(\d+) failed", output).group(1)) if re.search(r"(\d+) failed", output) else 0,
        "skipped": int(re.search(r"(\d+) skipped", output).group(1)) if re.search(r"(\d+) skipped", output) else 0,
        "errors": int(re.search(r"(\d+) error", output).group(1)) if re.search(r"(\d+) error", output) else 0,
    }


def parse_coverage_percent(output: str) -> float | None:
    """Extrai a cobertura total do pytest-cov sem confundir linhas de arquivos.

    O relatório com branches pode emitir linhas como:
    TOTAL 5318 1171 1162 213 74.29%

    O parser anterior capturava percentuais intermediários, como 29%, quando
    a linha final continha casas decimais. Este parser prioriza a linha TOTAL
    completa e depois a mensagem canônica `Total coverage: X%`.
    """
    total_matches = re.findall(
        r"(?im)^TOTAL\s+(?:\d+\s+)+(?P<percent>\d+(?:\.\d+)?)%\s*$",
        output,
    )
    if total_matches:
        return float(total_matches[-1])

    coverage_matches = re.findall(
        r"(?i)Total coverage:\s*(?P<percent>\d+(?:\.\d+)?)%",
        output,
    )
    if coverage_matches:
        return float(coverage_matches[-1])

    fail_under_matches = re.findall(
        r"(?i)Required test coverage of\s+\d+(?:\.\d+)?% reached\. Total coverage:\s*(?P<percent>\d+(?:\.\d+)?)%",
        output,
    )
    if fail_under_matches:
        return float(fail_under_matches[-1])

    return None


def run_tests_dimension() -> DimensionResult:
    started = datetime.now(timezone.utc)
    proc = run_command([sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"], cwd=BACKEND, env=backend_test_env())
    duration = (datetime.now(timezone.utc) - started).total_seconds()
    summary = parse_pytest_summary(proc.stdout + proc.stderr)
    total_failures = summary["failed"] + summary["errors"]
    passed = proc.returncode == 0 and total_failures == 0
    return DimensionResult(
        dimension="tests",
        status="passed" if passed else "failed",
        score=100.0 if passed else max(0.0, 100.0 - (total_failures * 5)),
        duration_seconds=round(duration, 2),
        summary=f"{summary['passed']} passed, {total_failures} failed",
        details={"exit_code": proc.returncode, "pytest_summary": summary, "stdout_tail": (proc.stdout + proc.stderr)[-2000:]},
        blockers=[f"{total_failures} test failure(s)"] if total_failures else [],
        recommendations=[] if passed else ["Corrigir testes falhos antes de merge"],
    )


def run_coverage_dimension(*, threshold: float = 60.0) -> DimensionResult:
    started = datetime.now(timezone.utc)
    proc = run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "--tb=line",
            "--cov=app",
            "--cov-report=term-missing:skip-covered",
            f"--cov-fail-under={int(threshold)}",
        ],
        cwd=BACKEND,
        env=backend_test_env(),
        timeout=900,
    )
    duration = (datetime.now(timezone.utc) - started).total_seconds()
    output = proc.stdout + proc.stderr
    coverage = parse_coverage_percent(output)
    passed = proc.returncode == 0 and coverage is not None and coverage >= threshold
    below_threshold = coverage is not None and coverage < threshold
    blockers: list[str] = []
    if below_threshold:
        blockers.append(f"coverage {coverage}% abaixo do gate {threshold}%")
    if proc.returncode != 0 and not below_threshold:
        blockers.append("pytest com cobertura falhou")
    if coverage is None:
        blockers.append("coverage total nao identificado no output pytest-cov")
    return DimensionResult(
        dimension="coverage",
        status="passed" if passed else "failed",
        score=round(coverage if coverage is not None else 0.0, 2),
        duration_seconds=round(duration, 2),
        summary=f"coverage {coverage if coverage is not None else 'n/a'}% (gate {threshold}%)",
        details={"exit_code": proc.returncode, "coverage_percent": coverage, "threshold_percent": threshold, "stdout_tail": output[-2000:]},
        blockers=blockers,
        recommendations=[] if passed else ["Aumentar cobertura em modulos criticos sem testes"],
    )


def run_mutation_dimension() -> DimensionResult:
    started = datetime.now(timezone.utc)
    targets = ["tests/test_public_smoke_routes.py", "tests/test_runtime_evidence_ingestion_contract.py", "tests/test_runtime_evidence_analytics.py"]
    existing = [target for target in targets if (BACKEND / target).exists()]
    if not existing:
        return DimensionResult("mutation", "failed", 0.0, 0.0, "nenhum alvo de mutation probe encontrado", {"targets": targets}, ["targets ausentes"], ["Garantir testes de contrato em rotas criticas"])
    proc = run_command([sys.executable, "-m", "pytest", *existing, "-q", "--tb=line"], cwd=BACKEND, env=backend_test_env())
    duration = (datetime.now(timezone.utc) - started).total_seconds()
    summary = parse_pytest_summary(proc.stdout + proc.stderr)
    total_failures = summary["failed"] + summary["errors"]
    passed = proc.returncode == 0 and total_failures == 0
    killed_mutations = summary["passed"]
    return DimensionResult(
        "mutation",
        "passed" if passed else "failed",
        round(min(100.0, killed_mutations * 10) if passed else max(0.0, killed_mutations * 5), 2),
        round(duration, 2),
        f"mutation probe em {len(existing)} modulos criticos",
        {"mode": "lightweight_probe", "targets": existing, "pytest_summary": summary, "exit_code": proc.returncode},
        [f"{total_failures} falha(s) no probe"] if total_failures else [],
        [] if passed else ["Reforcar testes de regressao em rotas publicas e contratos runtime"],
    )


def run_contract_dimension() -> DimensionResult:
    started = datetime.now(timezone.utc)
    blockers: list[str] = []
    recommendations: list[str] = []
    details: dict[str, Any] = {"checks": []}
    contract_tests = sorted((BACKEND / "tests").glob("test_*contract*.py"))
    repo_contract_tests = sorted((ROOT / "tests").glob("test_*contract*.py"))
    all_tests = [str(path.relative_to(ROOT)) for path in contract_tests] + [str(path.relative_to(ROOT)) for path in repo_contract_tests]
    if contract_tests:
        rel_tests = [str(path.relative_to(BACKEND)) for path in contract_tests]
        proc = run_command([sys.executable, "-m", "pytest", *rel_tests, "-q", "--tb=line"], cwd=BACKEND, env=backend_test_env())
        details["checks"].append({"name": "backend_contract_tests", "status": "passed" if proc.returncode == 0 else "failed", "tests": rel_tests, "summary": parse_pytest_summary(proc.stdout + proc.stderr)})
        if proc.returncode != 0:
            blockers.append("backend contract tests falharam")
    else:
        blockers.append("nenhum teste *contract* no backend")
    validator = ROOT / "scripts" / "artifact_contract_validator.py"
    if validator.exists():
        proc = run_command([sys.executable, str(validator)], cwd=ROOT)
        details["checks"].append({"name": "artifact_contract_validator", "status": "passed" if proc.returncode == 0 else "warning", "exit_code": proc.returncode})
        if proc.returncode != 0:
            recommendations.append("Revisar artifact_contract_validator em modo report-only")
    runtime_contract = CONTRACTS / "operational-json-artifact.schema.json"
    if runtime_contract.exists():
        try:
            json.loads(runtime_contract.read_text(encoding="utf-8"))
            details["checks"].append({"name": "operational_json_artifact_schema", "status": "passed"})
        except json.JSONDecodeError as exc:
            blockers.append(f"schema operacional invalido: {exc}")
    else:
        blockers.append("operational-json-artifact.schema.json ausente")
    duration = (datetime.now(timezone.utc) - started).total_seconds()
    hard_failures = [item for item in details["checks"] if item.get("status") == "failed"]
    status = "failed" if hard_failures or any("falharam" in b or "ausente" in b for b in blockers[:2]) else ("warning" if recommendations else "passed")
    score = 100.0 if status == "passed" else 70.0 if status == "warning" else 30.0
    return DimensionResult("contract", status, score, round(duration, 2), f"{len(all_tests)} contract test file(s), {len(details['checks'])} check(s)", {**details, "contract_test_files": all_tests}, blockers, recommendations)


def run_schema_dimension() -> DimensionResult:
    started = datetime.now(timezone.utc)
    blockers: list[str] = []
    details: dict[str, Any] = {"schemas_validated": 0, "schemas_failed": []}
    registry = ROOT / "docs" / "schema-registry.json"
    if registry.exists():
        try:
            registry_data = json.loads(registry.read_text(encoding="utf-8"))
            details["registry_version"] = registry_data.get("registry_version")
            details["required_gates"] = registry_data.get("governance", {}).get("required_gates", [])
        except json.JSONDecodeError as exc:
            blockers.append(f"schema-registry.json invalido: {exc}")
    else:
        blockers.append("schema-registry.json ausente")
    schema_files = sorted(CONTRACTS.glob("*.schema.json"))
    valid = 0
    for schema_path in schema_files:
        try:
            payload = json.loads(schema_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("root must be object")
            if "$schema" not in payload:
                details.setdefault("warnings", []).append(f"{schema_path.name} sem $schema")
            valid += 1
        except (json.JSONDecodeError, ValueError) as exc:
            details["schemas_failed"].append({"path": schema_path.name, "error": str(exc)})
    details["schemas_validated"] = valid
    details["schemas_total"] = len(schema_files)
    governance_script = ROOT / "tools" / "schema_governance" / "validate_schema_governance.py"
    if governance_script.exists():
        proc = run_command([sys.executable, str(governance_script)], cwd=ROOT, timeout=120)
        details["schema_governance_gate"] = {"status": "passed" if proc.returncode == 0 else "warning", "exit_code": proc.returncode}
        if proc.returncode != 0:
            details["schema_governance_tail"] = (proc.stdout + proc.stderr)[-1500:]
    duration = (datetime.now(timezone.utc) - started).total_seconds()
    if details["schemas_failed"]:
        blockers.append(f"{len(details['schemas_failed'])} schema(s) invalido(s)")
    status = "failed" if blockers else "passed"
    score = round((valid / len(schema_files) * 100) if schema_files else 0.0, 2)
    return DimensionResult("schema", status, score, round(duration, 2), f"{valid}/{len(schema_files)} schemas JSON validos", details, blockers, [] if status == "passed" else ["Corrigir schemas invalidos em docs/contracts/"])


def run_ci_watch_dimension() -> DimensionResult:
    started = datetime.now(timezone.utc)
    blockers: list[str] = []
    details: dict[str, Any] = {"checks": []}
    required_files = [".github/workflows/ci.yml", ".github/workflows/pr-ci-watch.yml", "scripts/pr_ci_watch.py"]
    for rel in required_files:
        path = ROOT / rel
        ok = path.exists()
        details["checks"].append({"file": rel, "exists": ok})
        if not ok:
            blockers.append(f"arquivo obrigatorio ausente: {rel}")
    pr_watch = ROOT / "scripts" / "pr_ci_watch.py"
    if pr_watch.exists():
        proc = run_command([sys.executable, "-m", "py_compile", str(pr_watch)])
        details["checks"].append({"name": "pr_ci_watch_compile", "status": "passed" if proc.returncode == 0 else "failed"})
        if proc.returncode != 0:
            blockers.append("pr_ci_watch.py nao compila")
    workflow = ROOT / ".github/workflows/pr-ci-watch.yml"
    if workflow.exists():
        text = workflow.read_text(encoding="utf-8")
        for marker in ("concurrency:", "exclude-run-id", "pr-ci-watch.json"):
            found = marker in text
            details["checks"].append({"marker": marker, "found": found})
            if not found:
                blockers.append(f"PR CI Watch sem guardrail: {marker}")
    duration = (datetime.now(timezone.utc) - started).total_seconds()
    status = "failed" if blockers else "passed"
    return DimensionResult("ci-watch", status, 100.0 if status == "passed" else max(0.0, 100.0 - len(blockers) * 20), round(duration, 2), "estrutura local do PR CI Watch validada" if status == "passed" else f"{len(blockers)} gap(s)", details, blockers, [] if status == "passed" else ["Restaurar guardrails do PR CI Watch"])


DIMENSION_RUNNERS: dict[str, Callable[[], DimensionResult]] = {
    "tests": run_tests_dimension,
    "coverage": run_coverage_dimension,
    "mutation": run_mutation_dimension,
    "contract": run_contract_dimension,
    "schema": run_schema_dimension,
    "ci-watch": run_ci_watch_dimension,
}


def merge_state(*statuses: str) -> str:
    ranked = sorted(statuses, key=lambda item: STATE_RANK.get(item, 1), reverse=True)
    return ranked[0] if ranked else "unknown"


def consolidate(dimension_reports: list[dict[str, Any]], *, repository: str, run_id: str) -> dict[str, Any]:
    dimensions = sorted(dimension_reports, key=lambda item: item.get("dimension", ""))
    statuses = [str(item.get("status") or "unknown") for item in dimensions]
    scores = [float(item.get("score") or 0.0) for item in dimensions]
    global_state = merge_state(*statuses)
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    blockers = [f"{item['dimension']}: {blocker}" for item in dimensions for blocker in item.get("blockers", [])]
    decision_map = {"passed": "continuar_incremento_qualidade", "warning": "validar_warnings_antes_de_merge", "failed": "bloquear_merge_ate_corrigir_qualidade"}
    return {
        "schema_version": "1.0.0",
        "trail": "D",
        "trail_name": "Qualidade e Governança",
        "generated_at": utc_now(),
        "correlation_id": str(uuid4()),
        "repository": repository,
        "run_id": run_id,
        "parallelizable": True,
        "dimensions_total": len(dimensions),
        "state": global_state,
        "decision": decision_map.get(global_state, "investigar"),
        "average_score": avg_score,
        "min_score": min(scores) if scores else 0.0,
        "max_score": max(scores) if scores else 0.0,
        "blockers": blockers,
        "dimensions": dimensions,
        "recommended_actions": _recommended_actions(global_state, dimensions),
        "mode": "report_only",
    }


def _recommended_actions(global_state: str, dimensions: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if global_state == "failed":
        actions.append({"priority": "P0", "action": "corrigir_dimensoes_falhas", "detail": "Trilha D com falha — revisar blockers por dimensao"})
    for item in dimensions:
        if item.get("status") == "failed":
            actions.append({"priority": "P1", "action": f"corrigir_{item['dimension']}", "detail": str(item.get("summary") or "")})
    if global_state == "passed":
        actions.append({"priority": "P3", "action": "manter_gates_ci_obrigatorio", "detail": "Trilha D verde — manter CI ReqSys v2 Enterprise como gate canonico"})
    return actions


def write_dimension_report(result: DimensionResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{result.dimension}.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_consolidated_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "trilha-d-qualidade-governanca.json"
    md_path = output_dir / "trilha-d-qualidade-governanca.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Trilha D — Qualidade e Governança", "", f"- Estado: **{report['state']}**", f"- Decisão: {report['decision']}", f"- Score médio: {report['average_score']}%", f"- Dimensões: {report['dimensions_total']}", f"- Paralelizável: {report['parallelizable']}", "", "## Dimensões", "", "| Dimensão | Status | Score | Resumo |", "|---|---|---:|---|"]
    for item in report["dimensions"]:
        lines.append(f"| {item['dimension']} | {item['status']} | {item['score']} | {item['summary']} |")
    if report["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {blocker}" for blocker in report["blockers"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def load_dimension_reports(output_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        path = output_dir / f"{dimension}.json"
        if path.exists():
            reports.append(json.loads(path.read_text(encoding="utf-8")))
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trilha D — Qualidade e Governança")
    parser.add_argument("--dimension", choices=[*DIMENSIONS, "all"], default="all", help="Dimensão a executar")
    parser.add_argument("--consolidate", action="store_true", help="Consolidar JSONs de dimensões")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "local/reqsys"))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--fail-on-error", action="store_true", help="Retorna exit code 1 quando estado consolidado for failed")
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    if args.consolidate:
        reports = load_dimension_reports(output_dir)
        if not reports:
            print("Nenhum relatório de dimensão encontrado para consolidar", file=sys.stderr)
            return 1
        consolidated = consolidate(reports, repository=args.repository, run_id=args.run_id)
        write_consolidated_report(consolidated, output_dir)
        print(json.dumps(consolidated, indent=2, ensure_ascii=False))
        if args.fail_on_error and consolidated["state"] == "failed":
            return 1
        return 0
    dimensions_to_run = DIMENSIONS if args.dimension == "all" else (args.dimension,)
    results: list[DimensionResult] = []
    exit_code = 0
    for name in dimensions_to_run:
        result = DIMENSION_RUNNERS[name]()
        write_dimension_report(result, output_dir)
        results.append(result)
        if result.status == "failed":
            exit_code = 1
    if args.dimension == "all":
        consolidated = consolidate([item.to_dict() for item in results], repository=args.repository, run_id=args.run_id)
        write_consolidated_report(consolidated, output_dir)
        print(json.dumps(consolidated, indent=2, ensure_ascii=False))
        if args.fail_on_error and consolidated["state"] == "failed":
            return 1
        return exit_code
    print(json.dumps(results[0].to_dict(), indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
