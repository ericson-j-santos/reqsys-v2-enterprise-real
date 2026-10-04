from app.services.lowcode_adr_coordinator import planejar_coordenacao_por_adr
from app.services.reqsys_orchestrator import OrchestratorDemand, classificar_demanda


def test_lowcode_never_marks_flyio_ready_for_dispatch():
    result = planejar_coordenacao_por_adr(
        objetivo="Reativar deploy Fly.io em producao",
        adr_refs=["ADR-036"],
        dry_run=False,
    )

    assert result["status"] == "blocked_permanent_retirement"
    assert result["roteamento"] == []
    assert result["flyio_retirement"]["status"] == "PERMANENTLY_RETIRED"
    assert result["flyio_retirement"]["external_dispatch_allowed"] is False


def test_reqsys_orchestrator_routes_flyio_only_to_retirement_evidence():
    result = classificar_demanda(
        OrchestratorDemand(
            titulo="Publicar novamente no Fly.io",
            descricao="Executar deploy e configurar secrets.",
        )
    )

    assert result["governanca"]["modo_execucao"] == "bloqueado"
    assert result["pipeline_sugerido"] is None
    assert result["automacoes_recomendadas"] == []
    assert result["flyio_retirement"]["dispatch_allowed"] is False


def test_provider_neutral_runtime_request_remains_available():
    result = classificar_demanda(
        OrchestratorDemand(
            titulo="Validar health do runtime",
            descricao="Coletar readiness e evidencia do ambiente Azure.",
        )
    )

    assert result["tema"] == "runtime"
    assert result["governanca"]["modo_execucao"] == "assistido"
    assert result["pipeline_sugerido"] == "runtime-health-validator"
