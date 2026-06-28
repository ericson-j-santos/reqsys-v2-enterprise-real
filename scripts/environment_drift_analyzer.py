#!/usr/bin/env python3
"""Cross-environment drift analyzer (dev / hml / prod).

Compares readiness probes and URL matrix alignment across canonical environments.
Report-only — does not block promotion automatically.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def classify_cross_env_drift(
    environments: list[dict[str, Any]],
    promotion_order: list[str],
) -> tuple[str, list[dict[str, Any]], list[str]]:
    findings: list[dict[str, Any]] = []
    recommendations: list[str] = []

    by_canonical = {item["canonical"]: item for item in environments if item.get("canonical")}
    promoted = [key for key in promotion_order if key in by_canonical]

    statuses = {key: by_canonical[key].get("status") for key in promoted}
    readiness = {
        key: float(by_canonical[key].get("readiness_percent") or 0)
        for key in promoted
        if by_canonical[key].get("readiness_percent") is not None
    }

    if "prod" in statuses and statuses.get("prod") == "ready":
        for env in ("dev", "hml"):
            if env in statuses and statuses[env] not in ("ready", "local_only"):
                findings.append(
                    {
                        "type": "promotion_inversion",
                        "severity": "high",
                        "detail": f"prod ready but {env} is {statuses[env]}",
                        "environments": [env, "prod"],
                    }
                )
                recommendations.append(f"Investigar degradacao em {env} antes de confiar em prod.")

    if readiness:
        values = list(readiness.values())
        spread = max(values) - min(values)
        if spread >= 50:
            findings.append(
                {
                    "type": "readiness_spread",
                    "severity": "medium",
                    "detail": f"readiness spread {spread}% across {list(readiness)}",
                    "environments": list(readiness),
                }
            )
            recommendations.append("Alinhar disponibilidade entre ambientes promoviveis.")

    for item in environments:
        if item.get("url_matrix_aligned") is False:
            findings.append(
                {
                    "type": "url_matrix_drift",
                    "severity": "high",
                    "detail": f"probe URLs divergem de infra/fly-environments.json ({item['canonical']})",
                    "environments": [item["canonical"]],
                }
            )
            recommendations.append(
                f"Normalizar URLs de {item['canonical']} entre validate_environments_readiness e fly-environments."
            )

    severities = [f.get("severity") for f in findings]
    if "high" in severities:
        drift_level = "ALTO"
        status = "degraded"
        risk = "high"
    elif "medium" in severities:
        drift_level = "MEDIO"
        status = "watch"
        risk = "medium"
    elif findings:
        drift_level = "BAIXO"
        status = "watch"
        risk = "low"
    else:
        drift_level = "NENHUM"
        status = "aligned"
        risk = "low"

    if not recommendations:
        recommendations.append("Ambientes alinhados — continuar monitoramento longitudinal.")

    return drift_level, findings, recommendations


def analyze(multi_env: dict[str, Any], commit_sha: str) -> dict[str, Any]:
    environments = multi_env.get("environments") or []
    promotion_order = (multi_env.get("summary") or {}).get("promotion_order") or ["dev", "hml", "prod"]
    drift_level, findings, recommendations = classify_cross_env_drift(environments, promotion_order)

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "environment-drift-analyzer",
        "status": "degraded" if drift_level in {"ALTO", "MEDIO"} else "ready",
        "confidence_level": "high" if environments else "low",
        "maturity_percent": multi_env.get("maturity_percent", 0),
        "operational_risk": "high" if drift_level == "ALTO" else "medium" if drift_level == "MEDIO" else "low",
        "commit_sha": commit_sha,
        "correlation_id": multi_env.get("correlation_id") or str(uuid4()),
        "mode": "report_only",
        "drift_level": drift_level,
        "findings": findings,
        "recommendations": recommendations,
        "blocked_actions": [
            "auto_block_production",
            "auto_rollback",
            "destructive_remediation",
        ],
        "environments_compared": [item.get("canonical") for item in environments],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze cross-environment drift.")
    parser.add_argument(
        "--multi-env",
        type=Path,
        default=Path("artifacts/operational-multi-environment/multi-environment-evidence.json"),
    )
    parser.add_argument("--commit-sha", default="local")
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/environment-drift-analyzer"))
    args = parser.parse_args()

    multi_env = load_json(args.multi_env, {"environments": [], "summary": {}})
    report = analyze(multi_env, args.commit_sha)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "environment-drift.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"drift_level={report['drift_level']} findings={len(report['findings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
