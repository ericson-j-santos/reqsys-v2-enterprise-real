#!/usr/bin/env python3
"""Refresh Trilha D artifact ingestion pipeline.

Orquestra o refresh de todos os JSONs downstream a partir do relatório
consolidado da Trilha D (incremento artifact_ingestion_refresh).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = "artifacts/trilha-d-qualidade-governanca/trilha-d-qualidade-governanca.json"
DEFAULT_HISTORY = "docs/ops-dashboard/data/trilha-d-history.json"
DEFAULT_PARETO = "docs/ops-dashboard/data/padrao-ouro-operational-pareto.json"
DEFAULT_PREDICTIVE = "docs/ops-dashboard/data/predictive-regression-gate.json"
DEFAULT_MONITORING = "docs/ops-dashboard/data/continuous-trilha-d-monitoring.json"
DEFAULT_MONITORING_HISTORY = "docs/ops-dashboard/data/continuous-trilha-d-monitoring-history.json"
DEFAULT_GOVERNANCE = "docs/ops-dashboard/data/governance-evidence-index.json"
DEFAULT_MERGE_READINESS_HISTORY = "docs/ops-dashboard/data/merge-readiness-history.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def refresh_artifacts(
    report_path: Path,
    *,
    repo_root: Path = ROOT,
    github_run_id: str | None = None,
    merge_readiness_report: Path | None = None,
    skip_merge_readiness: bool = False,
) -> dict[str, Any]:
    """Atualiza histórico, Pareto, gate preditivo, monitoramento e governança."""
    refreshed: list[str] = []
    report_path = report_path.resolve()
    if not report_path.exists():
        return {"ok": False, "error": "report_missing", "refreshed": refreshed}

    history_path = repo_root / DEFAULT_HISTORY
    history_path.parent.mkdir(parents=True, exist_ok=True)

    from scripts.build_trilha_d_history import ingest_report_into_history

    ingest_report_into_history(str(report_path), str(history_path))
    refreshed.append(str(history_path))

    from scripts.build_padrao_ouro_operational_pareto import main as pareto_main

    pareto_main(["--output", str(repo_root / DEFAULT_PARETO), "--trilha-d-history", str(history_path)])
    refreshed.append(str(repo_root / DEFAULT_PARETO))

    predictive_path = repo_root / DEFAULT_PREDICTIVE
    from scripts.predict_operational_regression import main as predict_main

    predict_main(
        [
            "--history-json",
            str(history_path),
            "--report-json",
            str(report_path),
            "--output",
            str(predictive_path),
            "--mode",
            "report_only",
            "--json",
        ]
    )
    refreshed.append(str(predictive_path))

    monitoring_path = repo_root / DEFAULT_MONITORING
    from scripts.build_continuous_trilha_d_monitoring import main as monitoring_main

    monitoring_main(
        [
            "--history-json",
            str(history_path),
            "--predictive-json",
            str(predictive_path),
            "--output",
            str(monitoring_path),
        ]
    )
    refreshed.append(str(monitoring_path))

    monitoring_history_path = repo_root / DEFAULT_MONITORING_HISTORY
    from scripts.build_continuous_trilha_d_monitoring_history import main as monitoring_history_main

    monitoring_history_main(
        [
            "--ingest-monitoring",
            str(monitoring_path),
            "--output",
            str(monitoring_history_path),
            "--run-id",
            github_run_id or "",
        ]
    )
    refreshed.append(str(monitoring_history_path))

    governance_path = repo_root / DEFAULT_GOVERNANCE
    from scripts.build_governance_evidence_index import main as governance_main

    gov_args = ["--output", str(governance_path), "--trilha-d-history", str(history_path)]
    if github_run_id:
        gov_args.extend(["--github-run-id", github_run_id])
    governance_main(gov_args)
    refreshed.append(str(governance_path))

    from scripts.build_trilha_d_history import load_history_from_output, write_payload

    history = load_history_from_output(history_path)
    write_payload(str(history_path), history=history, artifact_ingestion=True)

    pareto_main(["--output", str(repo_root / DEFAULT_PARETO), "--trilha-d-history", str(history_path)])

    if not skip_merge_readiness and merge_readiness_report and merge_readiness_report.exists():
        from scripts.build_merge_readiness_history import main as merge_main

        merge_main(
            [
                "--ingest-report",
                str(merge_readiness_report),
                "--output",
                str(repo_root / DEFAULT_MERGE_READINESS_HISTORY),
                "--run-id",
                github_run_id or "",
            ]
        )
        refreshed.append(str(repo_root / DEFAULT_MERGE_READINESS_HISTORY))

    artifact_dir = repo_root / "artifacts/trilha-d-qualidade-governanca"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for name, src in (
        ("predict-operational-regression-gate.json", predictive_path),
        ("continuous-trilha-d-monitoring.json", monitoring_path),
    ):
        if src.exists():
            (artifact_dir / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "ok": True,
        "refreshed_at": utc_now(),
        "refreshed": refreshed,
        "artifact_ingestion_refresh_enabled": True,
        "github_run_id": github_run_id,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh downstream artifacts da Trilha D.")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Relatório consolidado da Trilha D")
    parser.add_argument("--repo-root", default=str(ROOT), help="Raiz do repositório")
    parser.add_argument("--github-run-id", default="", help="Run ID do workflow para deep links")
    parser.add_argument(
        "--merge-readiness-report",
        default="",
        help="JSON opcional do gate merge-readiness para append no histórico",
    )
    parser.add_argument("--skip-merge-readiness", action="store_true")
    parser.add_argument("--json", action="store_true", help="Imprime resultado estruturado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    merge_report = Path(args.merge_readiness_report) if args.merge_readiness_report else None
    result = refresh_artifacts(
        Path(args.report),
        repo_root=Path(args.repo_root),
        github_run_id=args.github_run_id or None,
        merge_readiness_report=merge_report,
        skip_merge_readiness=args.skip_merge_readiness,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = "ok" if result.get("ok") else result.get("error", "failed")
        print(f"artifact_ingestion_refresh={status} files={len(result.get('refreshed') or [])}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
