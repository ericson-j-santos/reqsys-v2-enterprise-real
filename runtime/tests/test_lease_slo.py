from app.observability.lease_slo import avaliar_lease_slo


def test_lease_slo_saudavel_sem_violacoes() -> None:
    resultado = avaliar_lease_slo(
        {
            "lease_acquired_total": 100,
            "lease_contention_total": 5,
            "lease_renewed_total": 100,
            "lease_renew_failed_total": 0,
            "lease_expired_recovered_total": 0,
        }
    )

    assert resultado["status"] == "healthy"
    assert resultado["alerts"] == []


def test_lease_slo_alerta_contencao_falha_e_expiracao() -> None:
    resultado = avaliar_lease_slo(
        {
            "lease_acquired_total": 80,
            "lease_contention_total": 20,
            "lease_renewed_total": 90,
            "lease_renew_failed_total": 10,
            "lease_expired_recovered_total": 2,
        }
    )

    codigos = {alerta["codigo"] for alerta in resultado["alerts"]}
    assert resultado["status"] == "breached"
    assert codigos == {
        "lease_contention_high",
        "lease_renew_failure_high",
        "lease_expired_jobs_recovered",
    }
