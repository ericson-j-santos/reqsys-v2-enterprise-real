#!/usr/bin/env python3
"""Gera dashboard autocontido do Credential & Environment Control Plane."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: raiz JSON deve ser objeto")
    return payload


def build_dashboard(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    status = str(report.get("status") or "UNKNOWN")
    environments = report.get("environments") or {}
    rows: list[str] = []

    for environment, item in environments.items():
        if not isinstance(item, dict):
            continue
        for binding in item.get("bindings") or []:
            if not isinstance(binding, dict):
                continue
            binding_status = html.escape(str(binding.get("status") or "UNKNOWN"))
            css = (
                "ok"
                if binding_status == "AVAILABLE"
                else "bad"
                if binding_status in {"MISSING", "DEGRADED"}
                else "warn"
            )
            rows.append(
                "<tr>"
                f"<td><strong>{html.escape(str(environment).upper())}</strong></td>"
                f"<td>{html.escape(str(binding.get('credential_id') or ''))}</td>"
                f"<td>{html.escape(str(binding.get('provider') or ''))}</td>"
                f"<td><code>{html.escape(str(binding.get('reference') or ''))}</code></td>"
                f"<td>{html.escape(str(binding.get('consumer') or ''))}</td>"
                f"<td><span class='badge {css}'>{binding_status}</span></td>"
                f"<td>{html.escape(str(binding.get('reason') or ''))}</td>"
                "</tr>"
            )

    overall_css = (
        "ok" if status == "HEALTHY" else "bad" if status == "DEGRADED" else "warn"
    )
    pending = (
        int(summary.get("missing_bindings") or 0)
        + int(summary.get("degraded_bindings") or 0)
        + int(summary.get("unknown_bindings") or 0)
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReqSys — Control Plane de Ambientes e Credenciais</title>
<style>:root{{--bg:#f4f6f8;--card:#fff;--text:#17212b;--muted:#5f6b76;--line:#dfe5ea;--ok:#176b3a;--okbg:#e7f5ec;--warn:#8a5a00;--warnbg:#fff4d6;--bad:#9b1c1c;--badbg:#fdecec}}*{{box-sizing:border-box}}body{{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--text)}}main{{max-width:1280px;margin:auto;padding:28px 18px}}h1{{margin:0 0 4px}}p,.label,footer{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0}}.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}}.kpi{{font-size:26px;font-weight:700;margin-top:5px}}.badge{{display:inline-block;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:700}}.ok{{color:var(--ok);background:var(--okbg)}}.warn{{color:var(--warn);background:var(--warnbg)}}.bad{{color:var(--bad);background:var(--badbg)}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:10px 8px}}th{{color:var(--muted);font-size:11px;text-transform:uppercase}}code{{font-size:12px}}.notice{{border-left:4px solid var(--warn)}}footer{{margin-top:16px;font-size:12px}}@media(max-width:860px){{.grid{{grid-template-columns:1fr 1fr}}table{{display:block;overflow:auto}}}}</style></head>
<body><main><header><h1>Control Plane de Ambientes e Credenciais</h1><p>Visão operacional de metadados. Valores de tokens, senhas e secrets não são exibidos nem persistidos.</p></header>
<section class="grid"><div class="card"><div class="label">Estado</div><div class="kpi"><span class="badge {overall_css}">{html.escape(status)}</span></div></div><div class="card"><div class="label">Ambientes</div><div class="kpi">{int(summary.get('environments_total') or 0)}</div></div><div class="card"><div class="label">Bindings</div><div class="kpi">{int(summary.get('bindings_total') or 0)}</div></div><div class="card"><div class="label">Disponíveis</div><div class="kpi">{int(summary.get('available_bindings') or 0)}</div></div><div class="card"><div class="label">Pendências</div><div class="kpi">{pending}</div></div></section>
<section class="card"><h2>Credencial → ambiente → consumidor</h2><table><thead><tr><th>Ambiente</th><th>Credencial</th><th>Provedor</th><th>Referência</th><th>Consumidor</th><th>Status</th><th>Evidência</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section class="card notice" style="margin-top:12px"><strong>Guard rail:</strong> este painel é report-only. Ele não cria, altera, rotaciona ou revela secrets e não autoriza promoção automática.</section>
<footer>Contrato {html.escape(str(report.get('contract') or 'unknown'))} · schema {html.escape(str(report.get('schema_version') or 'unknown'))} · secret_values_exposed=false</footer></main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", type=Path, default=Path("artifacts/credential-control-plane/health.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/credential-control-plane/index.html"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_dashboard(load_json(args.health)), encoding="utf-8")
    print(json.dumps({"status": "generated", "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
