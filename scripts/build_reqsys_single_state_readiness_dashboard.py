#!/usr/bin/env python3
"""Build a self-contained executive readiness dashboard from ReqSys Single State evidence.

The generator is deterministic, offline and report-only. It renders the governed
consumer readiness contract without changing production, deployment or promotion decisions.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

DEFAULT_REPORT = Path("artifacts/reqsys-single-state-consumer-readiness/report.json")
DEFAULT_OUTPUT = Path("artifacts/reqsys-single-state-consumer-readiness/index.html")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def status_label(ready: bool) -> str:
    return "READY" if ready else "EVIDENCE INCOMPLETE"


def build_dashboard(report: dict[str, Any]) -> str:
    consumers = report.get("consumers") or {}
    rows: list[str] = []
    for name in ("governance", "runtime", "analytics"):
        item = consumers.get(name) or {}
        ready = bool(item.get("ready"))
        missing = ", ".join(map(str, item.get("missing_sections") or [])) or "Nenhuma"
        empty = ", ".join(map(str, item.get("empty_sections") or [])) or "Nenhuma"
        purpose = html.escape(str(item.get("purpose") or "Não informado"))
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(name.title())}</strong><br><small>{purpose}</small></td>"
            f"<td><span class='badge {'ok' if ready else 'warn'}'>{status_label(ready)}</span></td>"
            f"<td>{html.escape(missing)}</td>"
            f"<td>{html.escape(empty)}</td>"
            "</tr>"
        )

    readiness = float(report.get("readiness_percent") or 0)
    overall_ready = str(report.get("status")) == "READY"
    next_increment = html.escape(str(report.get("next_safe_increment") or "Não informado"))
    source = html.escape(str(report.get("source_contract") or "unknown"))
    schema = html.escape(str(report.get("source_schema_version") or "unknown"))

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ReqSys — Readiness do Estado Único</title>
<style>
:root {{ color-scheme: light; --bg:#f4f6f8; --card:#fff; --text:#17212b; --muted:#5f6b76; --line:#dfe5ea; --ok:#176b3a; --okbg:#e7f5ec; --warn:#8a5a00; --warnbg:#fff4d6; }}
* {{ box-sizing:border-box; }} body {{ margin:0; font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif; background:var(--bg); color:var(--text); }}
main {{ max-width:1100px; margin:0 auto; padding:32px 20px; }} header {{ margin-bottom:20px; }} h1 {{ margin:0 0 6px; font-size:28px; }} h2 {{ font-size:18px; margin:0 0 14px; }} p {{ margin:0; color:var(--muted); }}
.grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin:20px 0; }} .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; }}
.kpi {{ font-size:28px; font-weight:700; margin-top:6px; }} .label {{ color:var(--muted); font-size:13px; }}
.badge {{ display:inline-block; border-radius:999px; padding:4px 9px; font-size:12px; font-weight:700; }} .ok {{ color:var(--ok); background:var(--okbg); }} .warn {{ color:var(--warn); background:var(--warnbg); }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ text-align:left; vertical-align:top; border-bottom:1px solid var(--line); padding:12px 10px; }} th {{ color:var(--muted); font-size:12px; text-transform:uppercase; }} small {{ color:var(--muted); }}
.notice {{ border-left:4px solid {'var(--ok)' if overall_ready else 'var(--warn)'}; }} footer {{ margin-top:18px; font-size:12px; color:var(--muted); }}
@media (max-width:760px) {{ .grid {{ grid-template-columns:1fr 1fr; }} table {{ display:block; overflow-x:auto; }} }}
</style>
</head>
<body><main>
<header><h1>Readiness do Estado Único ReqSys</h1><p>Painel executivo canônico, auditável e report-only.</p></header>
<section class="grid">
<div class="card"><div class="label">Readiness geral</div><div class="kpi">{readiness:.2f}%</div></div>
<div class="card"><div class="label">Consumidores prontos</div><div class="kpi">{int(report.get('ready_consumers') or 0)}/{int(report.get('total_consumers') or 3)}</div></div>
<div class="card"><div class="label">Estado</div><div class="kpi"><span class="badge {'ok' if overall_ready else 'warn'}">{html.escape(str(report.get('status') or 'UNKNOWN'))}</span></div></div>
<div class="card"><div class="label">Produção</div><div class="kpi"><span class="badge ok">NÃO BLOQUEANTE</span></div></div>
</section>
<section class="card"><h2>Conformidade por consumidor</h2><table><thead><tr><th>Consumidor</th><th>Status</th><th>Seções ausentes</th><th>Seções vazias</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section class="card notice" style="margin-top:14px"><h2>Próximo incremento seguro</h2><p>{next_increment}</p></section>
<footer>Fonte: {source} · schema {schema} · modo report_only · automatic_promotion_allowed=false</footer>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ReqSys Single State readiness dashboard")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    dashboard = build_dashboard(load_json(args.report))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dashboard, encoding="utf-8")
    print(json.dumps({"status": "generated", "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
