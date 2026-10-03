#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from html import escape
from pathlib import Path
from typing import Any


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _is_comparable(item: dict[str, Any]) -> bool:
    return (item.get("window_comparability") or {}).get("comparable_to_baseline") is True


def _series_item(item: dict[str, Any]) -> dict[str, Any]:
    comparability = item.get("window_comparability") or {}
    return {
        "generated_at": item.get("generated_at"),
        "run_id": item.get("run_id"),
        "status": item.get("status"),
        "overall_signal": (item.get("baseline_comparison") or {}).get("overall_signal"),
        "comparable_to_baseline": comparability.get("comparable_to_baseline") is True,
        "comparability_reason_codes": comparability.get("reason_codes", []),
        "success_rate_percent": (item.get("current") or {}).get("success_rate_percent"),
        "failure_rate_percent": (item.get("current") or {}).get("failure_rate_percent"),
        "p95_seconds": (item.get("current") or {}).get("p95_seconds"),
        "cv_percent": (item.get("current") or {}).get("cv_percent"),
    }


def summarize_history(records: list[dict[str, Any]], lookback: int = 5) -> dict[str, Any]:
    ordered = sorted(records, key=lambda item: str(item.get("generated_at") or ""))
    comparable = [item for item in ordered if _is_comparable(item)]
    recent = comparable[-lookback:]
    recent_context = ordered[-lookback:]

    signals = [str((item.get("baseline_comparison") or {}).get("overall_signal") or "unknown") for item in recent]
    improved = signals.count("improved")
    regressed = signals.count("regressed")
    stable = signals.count("stable")

    if len(recent) < 3:
        sustainability = "insufficient_data"
    elif improved >= math.ceil(len(recent) * 0.6) and regressed == 0:
        sustainability = "sustained_improvement"
    elif regressed >= math.ceil(len(recent) * 0.4):
        sustainability = "regression_watch"
    else:
        sustainability = "mixed"

    current = [item.get("current") or {} for item in recent]
    return {
        "available": bool(records),
        "mode": "report-only",
        "creates_gate": False,
        "sustainability_basis": "comparable_to_baseline_only",
        "records": len(ordered),
        "comparable_records": len(comparable),
        "excluded_non_comparable_records": len(ordered) - len(comparable),
        "lookback": len(recent),
        "requested_lookback": lookback,
        "sustainability": sustainability,
        "signals": {
            "improved": improved,
            "stable": stable,
            "regressed": regressed,
            "unknown": signals.count("unknown"),
        },
        "recent_averages": {
            "success_rate_percent": _avg([float(item.get("success_rate_percent", 0)) for item in current]),
            "failure_rate_percent": _avg([float(item.get("failure_rate_percent", 0)) for item in current]),
            "p95_seconds": _avg([float(item.get("p95_seconds", 0)) for item in current]),
            "cv_percent": _avg([float(item.get("cv_percent", 0)) for item in current]),
        },
        "series": [_series_item(item) for item in recent],
        "recent_context": [_series_item(item) for item in recent_context],
    }


def enrich(output_dir: Path, history_path: Path) -> dict[str, Any]:
    summary = summarize_history(load_history(history_path))
    report_path = output_dir / "workflow-command-center.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["process_improvement_history"] = summary
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (output_dir / "ci-process-improvement-history.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = [
        "# Histórico de melhoria do processo CI",
        "",
        f"- Registros totais: `{summary['records']}`",
        f"- Registros comparáveis: `{summary['comparable_records']}`",
        f"- Registros excluídos da sustentabilidade: `{summary['excluded_non_comparable_records']}`",
        f"- Janela comparável recente: `{summary['lookback']}` de `{summary['requested_lookback']}` solicitados",
        f"- Sustentabilidade: `{summary['sustainability']}`",
        f"- Base da sustentabilidade: `{summary['sustainability_basis']}`",
        f"- Modo: `{summary['mode']}`",
        "",
        "## Médias recentes comparáveis",
        "",
        f"- Success rate: `{summary['recent_averages']['success_rate_percent']}%`",
        f"- Failure rate: `{summary['recent_averages']['failure_rate_percent']}%`",
        f"- P95: `{summary['recent_averages']['p95_seconds']}s`",
        f"- CV: `{summary['recent_averages']['cv_percent']}%`",
        "",
        "## Série comparável recente",
        "",
    ]
    for item in summary["series"]:
        md.append(
            f"- `{item['generated_at']}` run `{item['run_id']}` — `{item['overall_signal']}`; "
            f"success={item['success_rate_percent']}%; failure={item['failure_rate_percent']}%; "
            f"P95={item['p95_seconds']}s; CV={item['cv_percent']}%"
        )
    md.extend(["", "## Contexto recente completo", ""])
    for item in summary["recent_context"]:
        md.append(
            f"- `{item['generated_at']}` run `{item['run_id']}` — comparável=`{item['comparable_to_baseline']}`; "
            f"sinal=`{item['overall_signal']}`; motivos=`{item['comparability_reason_codes']}`"
        )
    (output_dir / "ci-process-improvement-history.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    html_path = output_dir / "workflow-command-center.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        rows = "".join(
            f"<tr><td>{escape(str(item['generated_at']))}</td><td>{escape(str(item['overall_signal']))}</td>"
            f"<td>{item['success_rate_percent']}%</td><td>{item['failure_rate_percent']}%</td>"
            f"<td>{item['p95_seconds']}s</td><td>{item['cv_percent']}%</td></tr>"
            for item in summary["series"]
        )
        section = (
            "<h2>Melhoria de processo CI</h2>"
            f"<p>Sustentabilidade: <strong>{escape(summary['sustainability'])}</strong> — "
            f"{summary['comparable_records']} comparáveis de {summary['records']} registros; "
            f"{summary['excluded_non_comparable_records']} excluídos da decisão.</p>"
            "<p>A sustentabilidade usa somente observações com "
            "<code>comparable_to_baseline=true</code>; as demais permanecem apenas como contexto histórico.</p>"
            "<table><thead><tr><th>Data</th><th>Sinal</th><th>Sucesso</th><th>Falha</th><th>P95</th><th>CV</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )
        html_path.write_text(html.replace("</body>", section + "\n</body>"), encoding="utf-8")
    return summary


def main() -> int:
    output_dir = Path(os.environ.get("COMMAND_CENTER_OUTPUT_DIR", "artifacts/workflow-command-center"))
    history_path = Path(os.environ.get("CI_PROCESS_HISTORY_PATH", "audit/history/ci-process-improvement-history.jsonl"))
    summary = enrich(output_dir, history_path)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
