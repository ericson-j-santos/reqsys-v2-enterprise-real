#!/usr/bin/env python3
"""Agrega os artefatos de auditoria do GitLab CI em um dashboard HTML autocontido.

Le os relatorios ja publicados em audit/ por outros jobs do pipeline
(gate operacional, bandit, pip-audit, npm audit, trivy, gitleaks) e produz
um resumo visual unico. Nunca inventa evidencia: um artefato ausente vira um
cartao "sem_evidencia" (cinza), nunca um "ok" silencioso.

Cores seguem o padrao do projeto (ADR-009): verde=ok, amarelo=atencao,
vermelho=erro, cinza=sem evidencia.
"""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATUS_COR = {
    "ok": "#1a7f37",
    "atencao": "#9a6700",
    "erro": "#cf222e",
    "sem_evidencia": "#6e7781",
}
STATUS_LABEL = {
    "ok": "OK",
    "atencao": "Atenção",
    "erro": "Erro",
    "sem_evidencia": "Sem evidência",
}


@dataclass(frozen=True)
class CartaoEvidencia:
    titulo: str
    status: str
    detalhe: str
    fonte: str


def _ler_json(caminho: Path) -> Any | None:
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def avaliar_gate_operacional(audit_dir: Path) -> list[CartaoEvidencia]:
    payload = _ler_json(audit_dir / "gitlab-operational-evidence.json")
    if payload is None or not isinstance(payload, dict):
        return [CartaoEvidencia("Gate operacional de evidências", "sem_evidencia", "gitlab-operational-evidence.json não encontrado", "validate_gitlab_operational_evidence.py")]
    cartoes = []
    for check in payload.get("checks", []):
        status = "ok" if check.get("passed") else "erro"
        cartoes.append(CartaoEvidencia(f"Gate — {check.get('name', '?')}", status, str(check.get("detail", "")), "gitlab-operational-evidence.json"))
    return cartoes or [CartaoEvidencia("Gate operacional de evidências", "sem_evidencia", "nenhum check reportado", "gitlab-operational-evidence.json")]


def avaliar_bandit(audit_dir: Path) -> CartaoEvidencia:
    payload = _ler_json(audit_dir / "gitlab-bandit-report.json")
    if payload is None or not isinstance(payload, dict):
        return CartaoEvidencia("SAST — bandit", "sem_evidencia", "gitlab-bandit-report.json não encontrado", "backend_sast_bandit")
    resultados = payload.get("results") or []
    graves = [r for r in resultados if isinstance(r, dict) and str(r.get("issue_severity", "")).upper() in {"HIGH", "MEDIUM"}]
    status = "erro" if graves else ("atencao" if resultados else "ok")
    return CartaoEvidencia("SAST — bandit", status, f"{len(resultados)} achados ({len(graves)} high/medium)", "backend_sast_bandit")


def avaliar_pip_audit(audit_dir: Path) -> CartaoEvidencia:
    payload = _ler_json(audit_dir / "gitlab-pip-audit-report.json")
    if payload is None:
        return CartaoEvidencia("Dependências Python — pip-audit", "sem_evidencia", "gitlab-pip-audit-report.json não encontrado", "backend_dependency_scanning_pip_audit")
    deps = payload if isinstance(payload, list) else (payload.get("dependencies") or [])
    vulneraveis = [d for d in deps if isinstance(d, dict) and d.get("vulns")]
    status = "erro" if vulneraveis else "ok"
    return CartaoEvidencia("Dependências Python — pip-audit", status, f"{len(vulneraveis)} pacotes vulneráveis de {len(deps)}", "backend_dependency_scanning_pip_audit")


def avaliar_npm_audit(audit_dir: Path) -> CartaoEvidencia:
    payload = _ler_json(audit_dir / "gitlab-npm-audit-report.json")
    if payload is None or not isinstance(payload, dict):
        return CartaoEvidencia("Dependências Frontend — npm audit", "sem_evidencia", "gitlab-npm-audit-report.json não encontrado", "frontend_dependency_scanning_npm_audit")
    vulns = (payload.get("metadata") or {}).get("vulnerabilities") or {}
    criticos = int(vulns.get("critical", 0)) + int(vulns.get("high", 0))
    total = sum(int(v) for v in vulns.values()) if vulns else 0
    status = "erro" if criticos else ("atencao" if total else "ok")
    detalhe = ", ".join(f"{k}={v}" for k, v in vulns.items()) or "sem dados de vulnerabilidade"
    return CartaoEvidencia("Dependências Frontend — npm audit", status, detalhe, "frontend_dependency_scanning_npm_audit")


def avaliar_trivy(audit_dir: Path) -> CartaoEvidencia:
    payload = _ler_json(audit_dir / "gitlab-trivy-report.json")
    if payload is None or not isinstance(payload, dict):
        return CartaoEvidencia("Container scanning — trivy", "sem_evidencia", "gitlab-trivy-report.json não encontrado", "container_scanning_trivy")
    resultados = payload.get("Results") or []
    total = sum(len(r.get("Vulnerabilities") or []) for r in resultados if isinstance(r, dict))
    status = "atencao" if total else "ok"
    return CartaoEvidencia("Container scanning — trivy", status, f"{total} vulnerabilidades HIGH/CRITICAL (informativo, não bloqueante)", "container_scanning_trivy")


def avaliar_gitleaks(audit_dir: Path) -> CartaoEvidencia:
    payload = _ler_json(audit_dir / "gitlab-secret-detection-report.json")
    if payload is None:
        return CartaoEvidencia("Secret detection — gitleaks", "sem_evidencia", "gitlab-secret-detection-report.json não encontrado", "secret_detection_gitleaks")
    achados = payload if isinstance(payload, list) else []
    status = "erro" if achados else "ok"
    return CartaoEvidencia("Secret detection — gitleaks", status, f"{len(achados)} segredos detectados", "secret_detection_gitleaks")


def montar_dashboard(audit_dir: Path) -> dict[str, Any]:
    cartoes = [
        *avaliar_gate_operacional(audit_dir),
        avaliar_bandit(audit_dir),
        avaliar_pip_audit(audit_dir),
        avaliar_npm_audit(audit_dir),
        avaliar_trivy(audit_dir),
        avaliar_gitleaks(audit_dir),
    ]
    contagem = Counter(cartao.status for cartao in cartoes)
    if contagem["erro"]:
        status_geral = "erro"
    elif contagem["atencao"]:
        status_geral = "atencao"
    elif contagem["ok"]:
        status_geral = "ok"
    else:
        status_geral = "sem_evidencia"
    return {
        "schema_version": "1.0.0",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "status_geral": status_geral,
        "contagem_por_status": dict(contagem),
        "cartoes": [cartao.__dict__ for cartao in cartoes],
    }


def render_html(dashboard: dict[str, Any]) -> str:
    cor_geral = STATUS_COR[dashboard["status_geral"]]
    linhas_cartoes = []
    for cartao in dashboard["cartoes"]:
        cor = STATUS_COR[cartao["status"]]
        label = STATUS_LABEL[cartao["status"]]
        linhas_cartoes.append(
            f"""<div class="cartao" style="border-left-color:{cor}">
  <div class="cartao-topo"><span class="badge" style="background:{cor}">{label}</span><h3>{html.escape(cartao['titulo'])}</h3></div>
  <p class="detalhe">{html.escape(cartao['detalhe'])}</p>
  <p class="fonte">fonte: {html.escape(cartao['fonte'])}</p>
</div>"""
        )
    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>GitLab Evidence Dashboard — ReqSys</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; background:#0d1117; color:#e6edf3; margin:0; padding:2rem; }}
  h1 {{ font-size:1.4rem; margin-bottom:0.2rem; }}
  .meta {{ color:#8b949e; font-size:0.85rem; margin-bottom:1.5rem; }}
  .status-geral {{ display:inline-block; padding:0.3rem 0.8rem; border-radius:999px; font-weight:600; color:#0d1117; background:{cor_geral}; margin-bottom:1.5rem; }}
  .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap:1rem; }}
  .cartao {{ background:#161b22; border:1px solid #30363d; border-left-width:4px; border-left-style:solid; border-radius:8px; padding:1rem; }}
  .cartao-topo {{ display:flex; align-items:center; gap:0.6rem; margin-bottom:0.5rem; }}
  .cartao-topo h3 {{ font-size:0.95rem; margin:0; }}
  .badge {{ color:#0d1117; font-size:0.7rem; font-weight:700; padding:0.15rem 0.5rem; border-radius:999px; text-transform:uppercase; }}
  .detalhe {{ font-size:0.85rem; color:#c9d1d9; margin:0.3rem 0; }}
  .fonte {{ font-size:0.75rem; color:#6e7781; margin:0; }}
</style>
</head>
<body>
<h1>GitLab Evidence Dashboard — ReqSys</h1>
<p class="meta">Gerado em {html.escape(dashboard['gerado_em'])}</p>
<div class="status-geral">Status geral: {STATUS_LABEL[dashboard['status_geral']]}</div>
<div class="grid">
{''.join(linhas_cartoes)}
</div>
</body>
</html>
"""


def write_outputs(dashboard: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gitlab-evidence-dashboard.json").write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "gitlab-evidence-dashboard.html").write_text(render_html(dashboard), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, default=Path("audit"))
    parser.add_argument("--output-dir", type=Path, default=Path("audit"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dashboard = montar_dashboard(args.audit_dir)
    write_outputs(dashboard, args.output_dir)
    print(json.dumps({"status_geral": dashboard["status_geral"], "contagem_por_status": dashboard["contagem_por_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
