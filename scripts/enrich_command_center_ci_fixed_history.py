#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path

from ci_fixed_window_sustainability import summarize_history

START = "<!-- CI_FIXED_HISTORY_START -->"
END = "<!-- CI_FIXED_HISTORY_END -->"


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def enrich(output_dir: Path, history_path: Path) -> dict:
    summary = summarize_history(load_history(history_path))
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "workflow-command-center.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    report["process_improvement_history"] = summary
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "ci-process-improvement-history.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    md = [
        "# Histórico de melhoria do processo CI",
        "",
        f"- Registros totais: `{summary['records']}`",
        f"- Janelas horárias elegíveis: `{summary['eligible_records']}`",
        f"- Excluídas da decisão: `{summary['excluded_ineligible_records']}`",
        f"- Política ativa: `{summary['active_policy_id']}`",
        f"- Sustentabilidade: `{summary['sustainability']}`",
        f"- Base: `{summary['sustainability_basis']}`",
        "- Baseline congelado de 02/09: `referência histórica descritiva`",
        "- Cria gate: `não`",
        "",
        "## Série horária elegível",
    ]
    for item in summary["series"]:
        md.append(
            f"- `{item['start_at']}` → `{item['end_at']}` — tendência=`{item['trend_signal']}`; "
            f"success={item['success_rate_percent']}%; failure={item['failure_rate_percent']}%; "
            f"P95={item['p95_seconds']}s; CV={item['cv_percent']}%"
        )
    md.extend(["", "## Contexto recente completo"])
    for item in summary["recent_context"]:
        md.append(
            f"- run `{item['run_id']}` — elegível=`{item['sample_eligible']}`; "
            f"política=`{item['policy_id']}`; cobertura=`{item['completion_coverage_percent']}`; "
            f"motivos=`{item['eligibility_reason_codes']}`"
        )
    (output_dir / "ci-process-improvement-history.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    html_path = output_dir / "workflow-command-center.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        if START in html and END in html:
            before = html.split(START, 1)[0]
            after = html.split(END, 1)[1]
            html = before + after
        rows = "".join(
            f"<tr><td>{escape(str(item['start_at']))}</td><td>{escape(str(item['trend_signal']))}</td>"
            f"<td>{item['success_rate_percent']}%</td><td>{item['failure_rate_percent']}%</td>"
            f"<td>{item['p95_seconds']}s</td><td>{item['cv_percent']}%</td></tr>"
            for item in summary["series"]
        )
        section = (
            START
            + "<h2>Melhoria de processo CI — janelas horárias</h2>"
            + f"<p>Sustentabilidade: <strong>{escape(summary['sustainability'])}</strong>; "
            + f"{summary['eligible_records']} janelas elegíveis.</p>"
            + "<p>Decisão baseada somente em janelas fixas homogêneas; o baseline congelado permanece histórico.</p>"
            + "<table><thead><tr><th>Início</th><th>Tendência</th><th>Sucesso</th><th>Falha</th><th>P95</th><th>CV</th>"
            + f"</tr></thead><tbody>{rows}</tbody></table>"
            + END
        )
        html_path.write_text(html.replace("</body>", section + "\n</body>"), encoding="utf-8")
    return summary


def main() -> int:
    output_dir = Path(os.environ.get("COMMAND_CENTER_OUTPUT_DIR", "artifacts/workflow-command-center"))
    history_path = Path(os.environ.get("CI_PROCESS_HISTORY_PATH", "audit/history/ci-process-improvement-history.jsonl"))
    print(json.dumps(enrich(output_dir, history_path), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
