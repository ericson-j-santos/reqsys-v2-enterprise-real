from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "teams-commit-notification.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_gateway_assinado_permanece_rota_primaria() -> None:
    text = workflow_text()

    assert "resolve_pc24x7_dev_locator.mjs --self-test" in text
    assert "steps.locator.outputs.base_url" in text
    assert 'delivery_mode=gateway' in text
    assert '"scripts/notificar_teams.py"' in text
    assert '"flow_bot"' in text
    assert '"--strict"' in text
    assert "vars.TEAMS_GATEWAY_BASE_URL" not in text
    assert "fly.io" not in text
    assert "fly.dev" not in text


def test_webhook_governado_e_fallback_pre_envio() -> None:
    text = workflow_text()

    assert "locator_rc=$?" in text
    assert 'echo "resolved=false"' in text
    assert "if: steps.locator.outputs.resolved == 'true'" in text
    assert "TEAMS_WEBHOOK_URL: ${{ secrets.TEAMS_WEBHOOK_URL }}" in text
    assert "TEAMS_WEBHOOK_RECIPIENT: ${{ secrets.TEAMS_WEBHOOK_RECIPIENT }}" in text
    assert 'elif [[ "$LOCATOR_RESOLVED" != "true"' in text
    assert 'delivery_mode=webhook_fallback' in text
    assert 'if delivery_mode == "gateway"' in text
    assert '"tools/geradores/teams_graph_gateway_autocontido.py"' in text
    assert '"send-webhook"' in text
    assert '"--adaptive-card-file"' in text
    assert '"commit-notification-fallback"' in text


def test_dupla_indisponibilidade_permanece_fail_closed() -> None:
    text = workflow_text()

    assert 'delivery_mode=unavailable' in text
    assert "Nenhuma rota Teams governada disponível" in text
    assert "Teams não confirmou envio pela rota" in text
    assert 'output.write(f"delivery_route={delivery_mode}\\n")' in text
    assert "continue-on-error:" not in text
    assert "concurrency:" not in text
