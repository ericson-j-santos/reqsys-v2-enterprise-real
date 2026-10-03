from __future__ import annotations

from typing import Any


def avaliar_lease_slo(metricas: dict[str, int]) -> dict[str, Any]:
    adquiridos = metricas.get("lease_acquired_total", 0)
    contencoes = metricas.get("lease_contention_total", 0)
    renovados = metricas.get("lease_renewed_total", 0)
    falhas_renovacao = metricas.get("lease_renew_failed_total", 0)
    recuperados = metricas.get("lease_expired_recovered_total", 0)

    tentativas_aquisicao = adquiridos + contencoes
    tentativas_renovacao = renovados + falhas_renovacao
    taxa_contencao = contencoes / tentativas_aquisicao if tentativas_aquisicao else 0.0
    taxa_falha_renovacao = falhas_renovacao / tentativas_renovacao if tentativas_renovacao else 0.0

    alertas: list[dict[str, Any]] = []
    if taxa_contencao > 0.10:
        alertas.append({"codigo": "lease_contention_high", "severidade": "warning", "valor": taxa_contencao, "limite": 0.10})
    if taxa_falha_renovacao > 0.01:
        alertas.append({"codigo": "lease_renew_failure_high", "severidade": "critical", "valor": taxa_falha_renovacao, "limite": 0.01})
    if recuperados > 0:
        alertas.append({"codigo": "lease_expired_jobs_recovered", "severidade": "warning", "valor": recuperados, "limite": 0})

    return {
        "status": "breached" if alertas else "healthy",
        "objectives": {
            "contention_rate_max": 0.10,
            "renew_failure_rate_max": 0.01,
            "expired_recovered_target": 0,
        },
        "indicators": {
            "contention_rate": round(taxa_contencao, 6),
            "renew_failure_rate": round(taxa_falha_renovacao, 6),
            "expired_recovered_total": recuperados,
        },
        "alerts": alertas,
    }
