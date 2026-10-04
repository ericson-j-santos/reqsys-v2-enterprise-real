#!/usr/bin/env python3
"""Gera dashboard e Adaptive Card para a evidência BACEN-04."""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
CONTROL_ID = "BACEN-04"


@dataclass(frozen=True)
class Outputs:
    json_path: Path
    markdown_path: Path
    html_path: Path
    card_path: Path


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def load_evidence(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"evidência não encontrada: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"evidência inválida: {exc}"
    if not isinstance(payload, dict):
        return None, "evidência deve ser um objeto JSON"
    return payload, None


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_count(data: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        snapshot = data.get(key)
        if isinstance(snapshot, dict) and isinstance(snapshot.get("row_count"), int):
            return int(snapshot["row_count"])
    return None


def evaluate(
    evidence: dict[str, Any] | None,
    workflow_status: str,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if workflow_status != "success":
        reasons.append(f"workflow_status={workflow_status}")
    if evidence is None:
        reasons.append("evidência ausente")
        return "critical", reasons

    if evidence.get("control_id") != CONTROL_ID:
        reasons.append("control_id inválido")
    if evidence.get("result") != "passed":
        reasons.append(f"result={evidence.get('result', 'ausente')}")
    if evidence.get("integrity_match") is not True:
        reasons.append("integridade não confirmada")
    if evidence.get("production_touched") is not False:
        reasons.append("produção pode ter sido acessada")

    rpo = _number(evidence.get("rpo_minutes"))
    rpo_target = _number(evidence.get("rpo_target_minutes"))
    if rpo is None or rpo_target is None:
        reasons.append("RPO ausente")
    elif rpo > rpo_target:
        reasons.append(f"RPO excedido: {rpo:g}>{rpo_target:g} min")

    rto = _number(evidence.get("rto_seconds"))
    rto_target = _number(evidence.get("rto_target_seconds"))
    if rto is None or rto_target is None:
        reasons.append("RTO ausente")
    elif rto > rto_target:
        reasons.append(f"RTO excedido: {rto:g}>{rto_target:g} s")

    if reasons:
        return "critical", reasons
    return "healthy", ["backup e restauração validados dentro dos limites"]


def build_dashboard(
    evidence: dict[str, Any] | None,
    *,
    evidence_error: str | None,
    workflow_status: str,
    repository: str,
    sha: str,
    run_url: str,
    generated_at: str,
    next_scheduled_at: str,
) -> dict[str, Any]:
    health, reasons = evaluate(evidence, workflow_status)
    data = evidence or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "control_id": CONTROL_ID,
        "health": health,
        "workflow_status": workflow_status,
        "generated_at": generated_at,
        "repository": repository,
        "commit_sha": sha,
        "run_url": run_url,
        "next_scheduled_at": next_scheduled_at,
        "reasons": reasons,
        "evidence_error": evidence_error,
        "metrics": {
            "result": data.get("result", "unavailable"),
            "integrity_match": data.get("integrity_match"),
            "rpo_minutes": data.get("rpo_minutes"),
            "rpo_target_minutes": data.get("rpo_target_minutes"),
            "rto_seconds": data.get("rto_seconds"),
            "rto_target_seconds": data.get("rto_target_seconds"),
            "source_row_count": _row_count(
                data,
                "source_integrity",
                "source_snapshot",
            ),
            "target_row_count": _row_count(
                data,
                "restored_integrity",
                "target_snapshot",
            ),
            "backup_sha256": data.get("backup_sha256"),
            "correlation_id": data.get("correlation_id"),
            "production_touched": data.get("production_touched"),
        },
    }


def _display(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "sim" if value else "não"
    return f"{value}{suffix}"


def build_markdown(dashboard: dict[str, Any]) -> str:
    metrics = dashboard["metrics"]
    symbol = "🟢" if dashboard["health"] == "healthy" else "🔴"
    rpo = (
        f"{_display(metrics['rpo_minutes'], ' min')} / "
        f"{_display(metrics['rpo_target_minutes'], ' min')}"
    )
    rto = (
        f"{_display(metrics['rto_seconds'], ' s')} / "
        f"{_display(metrics['rto_target_seconds'], ' s')}"
    )
    rows = [
        ("Saúde", f"**{dashboard['health']}**"),
        ("Workflow", f"`{dashboard['workflow_status']}`"),
        ("Resultado", f"`{metrics['result']}`"),
        ("Integridade", f"`{_display(metrics['integrity_match'])}`"),
        ("RPO medido / alvo", f"`{rpo}`"),
        ("RTO medido / alvo", f"`{rto}`"),
        (
            "Registros origem / destino",
            f"`{_display(metrics['source_row_count'])} / "
            f"{_display(metrics['target_row_count'])}`",
        ),
        ("Produção acessada", f"`{_display(metrics['production_touched'])}`"),
        ("Próxima execução", f"`{dashboard['next_scheduled_at']}`"),
        ("Commit", f"`{dashboard['commit_sha'][:12]}`"),
        ("Correlation ID", f"`{_display(metrics['correlation_id'])}`"),
    ]
    table = ["| Indicador | Valor |", "|---|---|"]
    table.extend(f"| {label} | {value} |" for label, value in rows)
    reasons = "<br>".join(str(item) for item in dashboard["reasons"])
    sections = [
        f"# {symbol} Dashboard BACEN-04 — Backup e Restauração",
        "",
        f"> Atualizado automaticamente em `{dashboard['generated_at']}`.",
        "",
        *table,
        "",
        f"**Diagnóstico:** {reasons}",
        "",
        f"[Abrir execução]({dashboard['run_url']})",
        "",
        "## Critérios de conformidade",
        "",
        "- restauração real em PostgreSQL isolado;",
        "- integridade origem/destino obrigatória;",
        "- RPO e RTO abaixo dos limites;",
        "- produção não acessada;",
        "- artifact JSON/HTML retido;",
        "- notificação no Teams com correlation ID.",
    ]
    return "\n".join(sections) + "\n"


def build_html(dashboard: dict[str, Any]) -> str:
    metrics = dashboard["metrics"]
    reasons = ", ".join(str(item) for item in dashboard["reasons"])
    rows = [
        ("Saúde", dashboard["health"]),
        ("Workflow", dashboard["workflow_status"]),
        ("Resultado", metrics["result"]),
        ("Integridade", _display(metrics["integrity_match"])),
        (
            "RPO",
            f"{_display(metrics['rpo_minutes'])} / "
            f"{_display(metrics['rpo_target_minutes'])} min",
        ),
        (
            "RTO",
            f"{_display(metrics['rto_seconds'])} / "
            f"{_display(metrics['rto_target_seconds'])} s",
        ),
        (
            "Registros origem/destino",
            f"{_display(metrics['source_row_count'])} / "
            f"{_display(metrics['target_row_count'])}",
        ),
        ("Produção acessada", _display(metrics["production_touched"])),
        ("Próxima execução", dashboard["next_scheduled_at"]),
        ("Correlation ID", _display(metrics["correlation_id"])),
    ]
    table = "".join(
        f"<tr><th>{html.escape(str(label))}</th>"
        f"<td>{html.escape(str(value))}</td></tr>"
        for label, value in rows
    )
    accent = "#1a7f37" if dashboard["health"] == "healthy" else "#cf222e"
    run_url = html.escape(dashboard["run_url"], quote=True)
    generated_at = html.escape(dashboard["generated_at"])
    commit = html.escape(dashboard["commit_sha"][:12])
    health = html.escape(dashboard["health"].upper())
    diagnosis = html.escape(reasons)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dashboard BACEN-04</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f6f8fa;color:#1f2328}}
main{{max-width:920px;margin:32px auto;padding:0 16px}}
.card{{background:white;border:1px solid #d0d7de;border-radius:12px;padding:24px}}
.status{{display:inline-block;padding:6px 12px;border-radius:999px;color:white}}
.status{{background:{accent};font-weight:700}}
table{{width:100%;border-collapse:collapse;margin-top:20px}}
th,td{{padding:12px;border-bottom:1px solid #d8dee4;text-align:left}}
th{{width:38%}}a{{color:#0969da}}small{{color:#57606a}}
</style>
</head>
<body><main><section class="card">
<h1>Backup e Restauração — BACEN-04</h1>
<p><span class="status">{health}</span></p>
<table>{table}</table>
<p><strong>Diagnóstico:</strong> {diagnosis}</p>
<p><a href="{run_url}">Abrir execução no GitHub Actions</a></p>
<small>Atualizado em {generated_at} · commit {commit}</small>
</section></main></body></html>"""


def build_card(dashboard: dict[str, Any]) -> dict[str, Any]:
    metrics = dashboard["metrics"]
    healthy = dashboard["health"] == "healthy"
    title = (
        "ReqSys — backup e restauração saudáveis"
        if healthy
        else "ReqSys — falha em backup/restauração"
    )
    rpo = (
        f"{_display(metrics['rpo_minutes'])} / "
        f"{_display(metrics['rpo_target_minutes'])} min"
    )
    rto = (
        f"{_display(metrics['rto_seconds'])} / "
        f"{_display(metrics['rto_target_seconds'])} s"
    )
    facts = [
        {"title": "Controle", "value": CONTROL_ID},
        {"title": "Saúde", "value": dashboard["health"]},
        {"title": "Resultado", "value": str(metrics["result"])},
        {"title": "Integridade", "value": _display(metrics["integrity_match"])},
        {"title": "RPO", "value": rpo},
        {"title": "RTO", "value": rto},
        {
            "title": "Produção acessada",
            "value": _display(metrics["production_touched"]),
        },
        {"title": "Próxima execução", "value": dashboard["next_scheduled_at"]},
        {"title": "Correlation ID", "value": _display(metrics["correlation_id"])},
    ]
    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "msteams": {"width": "Full"},
        "body": [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Large",
                "color": "Good" if healthy else "Attention",
                "wrap": True,
            },
            {"type": "FactSet", "facts": facts},
            {
                "type": "TextBlock",
                "text": "; ".join(str(item) for item in dashboard["reasons"]),
                "wrap": True,
                "isSubtle": True,
            },
        ],
        "actions": [
            {
                "type": "Action.OpenUrl",
                "title": "Abrir execução",
                "url": dashboard["run_url"],
            }
        ],
    }


def write_outputs(outputs: Outputs, dashboard: dict[str, Any]) -> None:
    paths = (
        outputs.json_path,
        outputs.markdown_path,
        outputs.html_path,
        outputs.card_path,
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    outputs.json_path.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    outputs.markdown_path.write_text(build_markdown(dashboard), encoding="utf-8")
    outputs.html_path.write_text(build_html(dashboard), encoding="utf-8")
    outputs.card_path.write_text(
        json.dumps(build_card(dashboard), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument(
        "--workflow-status",
        choices=["success", "failure", "cancelled", "skipped", "unknown"],
        required=True,
    )
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--generated-at", default=utc_now_iso())
    parser.add_argument("--next-scheduled-at", required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--html-output", type=Path, required=True)
    parser.add_argument("--card-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence, evidence_error = load_evidence(args.evidence)
    dashboard = build_dashboard(
        evidence,
        evidence_error=evidence_error,
        workflow_status=args.workflow_status,
        repository=args.repository,
        sha=args.sha,
        run_url=args.run_url,
        generated_at=args.generated_at,
        next_scheduled_at=args.next_scheduled_at,
    )
    write_outputs(
        Outputs(
            args.json_output,
            args.markdown_output,
            args.html_output,
            args.card_output,
        ),
        dashboard,
    )
    print(
        json.dumps(
            {"health": dashboard["health"], "outputs": True},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
