#!/usr/bin/env python3
"""Validação operacional rápida pós-merge — executa a malha P0 em um único processo.

Substitui a cascata workflow_run (dezenas de runs cancelados por merge) por um caminho
síncrono que conclui em segundos e publica todos os artifacts de uma vez.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.operational_alert_intelligence import build_payload as build_alert_payload, write_report as write_alert_report
from scripts.operational_runtime_mesh_hub import (
    build_payload as build_mesh_payload,
    hydrate_context,
    render_html as render_mesh_html,
    render_markdown as render_mesh_markdown,
)
from scripts.unified_operational_event_bus import build_payload as build_event_payload, write_report as write_event_report
from scripts.unified_operational_signal_consolidator import build_snapshot, write_report as write_signal_report


def _write_mesh_report(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "operational-runtime-mesh-hub.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "operational-runtime-mesh-hub.md").write_text(render_mesh_markdown(payload), encoding="utf-8")
    (output_dir / "operational-runtime-mesh-hub.html").write_text(render_mesh_html(payload), encoding="utf-8")


def _mirror_artifacts(root: Path, name: str, src: Path) -> None:
    target = root / "artifacts" / name
    target.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_file():
            (target / item.name).write_text(item.read_text(encoding="utf-8"), encoding="utf-8")


def _run_guardrail_checks(root: Path) -> list[str]:
    errors: list[str] = []
    required_files = [
        ".github/workflows/main-smoke-ci.yml",
        ".github/workflows/pr-scope-labeler.yml",
        ".github/workflows/pr-ci-watch.yml",
        ".github/workflows/ci-fast-operational.yml",
        ".github/workflows/main-operational-health.yml",
        "scripts/pr_ci_watch.py",
        "tests/test_pr_ci_watch.py",
        "docs/runbooks/main-smoke-ci.md",
        "docs/runbooks/pr-ci-watch.md",
        "config/operational-gaps-registry.json",
    ]
    for relative in required_files:
        if not (root / relative).exists():
            errors.append(f"arquivo ausente: {relative}")

    grep_checks = [
        ("read-only", root / ".github/workflows/pr-scope-labeler.yml"),
        ("sem mutacao de labels", root / ".github/workflows/pr-scope-labeler.yml"),
        ("main-smoke-ci-evidence", root / ".github/workflows/main-smoke-ci.yml"),
        ('environment_change":False', root / ".github/workflows/main-smoke-ci.yml"),
        ('deploy":False', root / ".github/workflows/main-smoke-ci.yml"),
        ("--exclude-run-id", root / ".github/workflows/pr-ci-watch.yml"),
        ("upload-artifact", root / ".github/workflows/pr-ci-watch.yml"),
    ]
    for needle, path in grep_checks:
        if needle.lower() not in path.read_text(encoding="utf-8").lower():
            errors.append(f"guardrail ausente em {path}: {needle}")

    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(root / "scripts/pr_ci_watch.py")],
        capture_output=True,
        text=True,
    )
    if compile_result.returncode != 0:
        errors.append(f"py_compile pr_ci_watch: {compile_result.stderr.strip()}")

    return errors


def run_fast_validation(
    *,
    repo: str,
    branch: str,
    sha: str,
    run_id: str,
    workflow_url: str,
    root: Path,
    output_dir: Path,
    skip_pytest: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    correlation_id = str(uuid4())
    errors = _run_guardrail_checks(root)
    if errors:
        raise RuntimeError("guardrails falharam: " + "; ".join(errors))

    if not skip_pytest:
        pytest_result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_pr_ci_watch.py", "-q"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if pytest_result.returncode != 0:
            raise RuntimeError(f"pytest pr_ci_watch falhou: {pytest_result.stdout}\n{pytest_result.stderr}")

    source_workflow = "Main Operational Validation Fast"
    mesh_dir = output_dir / "operational-runtime-mesh-hub"
    alert_dir = output_dir / "operational-alert-intelligence"
    event_dir = output_dir / "unified-operational-event-bus"
    signal_dir = output_dir / "unified-operational-signal-consolidator"
    health_dir = output_dir / "main-operational-health"

    mesh_payload = build_mesh_payload(
        source_workflow,
        "success",
        hydration_context=hydrate_context(root),
    )
    _write_mesh_report(mesh_payload, mesh_dir)

    write_alert_report(
        build_alert_payload(source_workflow, "success", branch=branch, commit=sha, workflow_url=workflow_url),
        alert_dir,
    )

    write_event_report(
        build_event_payload(
            source_workflow,
            "success",
            branch=branch,
            commit=sha,
            workflow_url=workflow_url,
            run_id=run_id,
            run_attempt="1",
            event_name="push",
        ),
        event_dir,
    )

    analytics_script = root / "tools/product_intelligence/generate_github_runtime_analytics.py"
    if analytics_script.exists():
        subprocess.run([sys.executable, str(analytics_script)], cwd=root, check=False)

    for name, src in [
        ("operational-runtime-mesh-hub", mesh_dir),
        ("operational-alert-intelligence", alert_dir),
        ("unified-operational-event-bus", event_dir),
    ]:
        _mirror_artifacts(root, name, src)

    snapshot = build_snapshot(repo, branch, root, correlation_id)
    write_signal_report(snapshot, signal_dir)

    health_dir.mkdir(parents=True, exist_ok=True)
    health_dir.joinpath("summary.md").write_text(
        "# Main Operational Health (fast path)\n\nValidação síncrona pós-merge.\n",
        encoding="utf-8",
    )
    health_dir.joinpath("evidence.json").write_text(
        json.dumps(
            {
                "workflow": source_workflow,
                "branch": branch,
                "sha": sha,
                "run_id": run_id,
                "environment_change": False,
                "deploy": False,
                "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "correlation_id": correlation_id,
                "fast_path": True,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    summary = {
        "schema_version": "1.0.0",
        "workflow": source_workflow,
        "correlation_id": correlation_id,
        "repository": repo,
        "branch": branch,
        "sha": sha,
        "run_id": run_id,
        "workflow_url": workflow_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": elapsed_ms,
        "fast_path": True,
        "overall_state": snapshot.get("overall_state"),
        "mesh_integrated": snapshot.get("mesh_integrated"),
        "evidence_gate_consolidated": (snapshot.get("evidence_gate_consolidated") or {}).get("consolidated"),
        "maturity_percent": snapshot.get("maturity_percent"),
        "guardrails_ok": True,
        "mode": "report_only",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "main-operational-validation-fast.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / "main-operational-validation-fast.md").write_text(
        "\n".join(
            [
                "# Main Operational Validation Fast",
                "",
                f"- Elapsed: **{elapsed_ms} ms**",
                f"- Overall state: `{summary['overall_state']}`",
                f"- Mesh integrated: `{summary['mesh_integrated']}`",
                f"- Evidence gate consolidated: `{summary['evidence_gate_consolidated']}`",
                f"- Maturity: `{summary['maturity_percent']}%`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validação operacional rápida pós-merge.")
    parser.add_argument("--repo", default="local/reqsys")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--sha", default="")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--workflow-url", default="")
    parser.add_argument("--root", type=Path, default=ROOT_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/main-operational-validation-fast"))
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = run_fast_validation(
            repo=args.repo,
            branch=args.branch,
            sha=args.sha,
            run_id=args.run_id,
            workflow_url=args.workflow_url,
            root=args.root,
            output_dir=args.output_dir,
            skip_pytest=args.skip_pytest,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            f"OK elapsed={summary['elapsed_ms']}ms "
            f"state={summary['overall_state']} mesh={summary['mesh_integrated']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
