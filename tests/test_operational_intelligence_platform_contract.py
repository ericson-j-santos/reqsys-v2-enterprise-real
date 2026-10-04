from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_operational_intelligence_core_esta_integrado_no_bootstrap_atual() -> None:
    main = read("backend/app/main.py")
    api = read("backend/app/api/operational_intelligence.py")

    assert "operational_intelligence" in main
    assert "app.include_router(operational_intelligence.router)" in main
    assert '@router.get("/runtime/health")' in api
    assert '@router.post("/runtime/diagnostico")' in api


def test_operational_intelligence_preserva_diagnostico_e_acao_governada() -> None:
    runtime = read("backend/app/services/runtime_intelligence_service.py")
    autonomous = read("backend/app/services/autonomous_operation_service.py")
    models = read("backend/app/models/operational_intelligence_models.py")

    assert "class RuntimeIntelligenceService" in runtime
    assert "score = max(0, min(100, score))" in runtime
    assert "class AutonomousOperationService" in autonomous
    assert '"exige_aprovacao": True' in autonomous
    assert "class StatusOperacional" in models


def test_telemetria_e_ui_usam_superficies_canonicas_atuais() -> None:
    telemetry = read("backend/app/core/telemetry.py")
    ui = read("frontend/src/views/MonitoramentoOperacionalView.vue")

    assert "log_evento" in telemetry
    assert "correlation" in ui.lower()
    assert "Monitoramento Operacional" in ui


def test_testes_criticos_cobrem_health_e_diagnostico() -> None:
    tests = read("backend/tests/test_operational_intelligence_critical_paths.py")

    assert "test_runtime_health_endpoint_expoe_capabilities" in tests
    assert "test_runtime_diagnostico_endpoint_integra_servicos" in tests
