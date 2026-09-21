import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "human_pending_satellite.py"
spec = importlib.util.spec_from_file_location("human_pending_satellite", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_detects_real_external_evidence():
    categories = module.classify(
        "HUMANO: disponibilizar corpus real",
        "exige revisão humana registrada e evidência real",
    )
    assert "real_external_evidence" in categories


def test_technical_ci_failure_alone_is_not_human():
    assert module.classify("CI vermelho no CodeQL", "build failed") == []


def test_technical_prod_issue_with_permission_mention_is_not_escalated():
    categories = module.classify(
        "[P0][STATUS] Regularizar dashboard público Teams e Control Center PROD",
        "Rotas retornam 404. Pode exigir permissão de deploy para PROD, caso o código já esteja correto.",
    )
    assert categories == []


def test_explicit_human_entra_bootstrap_is_detected():
    categories = module.classify(
        "Ativar Central de Conversas IA via Azure Bot em DEV",
        "A criação da identidade permanece como ação humana única e exige permissão Entra.",
    )
    assert "permission" in categories


def test_generic_future_human_approval_is_not_current_action():
    assert module.classify(
        "TODO operacional",
        "Produção permanece bloqueada. Aprovação humana continua obrigatória antes de promoção.",
    ) == []


def test_future_reboot_approval_does_not_alert_early():
    assert module.classify(
        "Piloto DEV",
        "Recuperação após reinício deve ser validada mediante aprovação humana explícita no momento do teste.",
    ) == []


def test_responsavel_heading_alone_is_not_human_intent():
    categories = module.classify(
        "Decisão de arquitetura documentada pelo Coordinator",
        "### Responsável\nericson-j-santos\nA decisão arquitetural será tratada pelo fluxo automático.",
    )
    assert categories == []


def test_generic_real_evidence_phrase_alone_is_not_human():
    assert module.classify(
        "E2E técnico",
        "O Coordinator deve coletar evidência real automaticamente após o teste.",
    ) == []


def test_external_corporate_sql_source_remains_human_dependency():
    categories = module.classify(
        "P0 — fornecer consulta SQL real",
        "A dependência mínima externa continua sendo fonte SQL corporativa e consulta real de negócio.",
    )
    assert "external_business_input" in categories


def test_resolved_human_gate_label_suppresses_stale_body():
    categories = module.classify(
        "HUMANO: bootstrap antigo",
        "A ação humana mínima exige permissão Entra.",
        {"human-gate:resolved"},
    )
    assert categories == []


def test_trusted_comment_can_clear_stale_human_gate():
    comments = [{
        "body": (
            "Gate administrativo concluído. Não existe ação manual indispensável ativa "
            "nesta issue neste momento."
        ),
        "author_association": "OWNER",
    }]
    assert module.human_gate_state_from_comments(comments) == "cleared"


def test_later_trusted_comment_can_reopen_cleared_human_gate():
    comments = [
        {
            "body": "Gate administrativo concluído. Não existe ação manual indispensável ativa.",
            "author_association": "OWNER",
        },
        {
            "body": "Gate humano atual: ação humana mínima para aprovação externa.",
            "author_association": "OWNER",
        },
    ]
    assert module.human_gate_state_from_comments(comments) == "active"


def test_untrusted_comment_cannot_clear_human_gate():
    comments = [{
        "body": "Gate administrativo concluído. Não notificar esta issue como pendência humana.",
        "author_association": "NONE",
    }]
    assert module.human_gate_state_from_comments(comments) is None


def test_external_business_finding_has_actionable_instruction():
    issue = {
        "number": 1649,
        "title": "P0 — fornecer consulta SQL real",
        "body": "A dependência mínima externa continua sendo fonte SQL corporativa.",
        "html_url": "https://example.test/issues/1649",
    }
    finding = module.build_finding(issue, [], ["external_business_input"])
    assert finding.environment == "DEV corporativo / integração externa"
    assert finding.risk == "alto"
    assert "fonte SQL/DSN ou RDL/RDS corporativa autorizada" in finding.action_text
    assert "Não publique segredo" in finding.action_text


def test_explicit_owner_approval_is_captured():
    comment = {
        "body": "Aprovo e autorizo a continuidade controlada.",
        "author_association": "OWNER",
        "html_url": "https://example.test/comment/1",
    }
    assert module.explicit_approval(comment) is True


def test_untrusted_approval_is_not_captured():
    comment = {
        "body": "Aprovo.",
        "author_association": "NONE",
        "html_url": "https://example.test/comment/2",
    }
    assert module.explicit_approval(comment) is False


def test_notification_marker_is_idempotent():
    issue = {
        "number": 1420,
        "title": "HUMANO: corpus real",
        "body": "corpus real e revisão humana",
        "html_url": "https://example.test/issues/1420",
        "updated_at": "2026-09-12T00:00:00Z",
    }
    finding = module.build_finding(issue, [], ["real_external_evidence"])
    comments = [{"body": module.render_comment(finding)}]
    assert module.already_notified(comments, finding) is True


def test_issue_updated_at_change_from_own_comment_does_not_change_signature():
    base = {
        "number": 1420,
        "title": "HUMANO: corpus real",
        "body": "corpus real e revisão humana",
        "html_url": "https://example.test/issues/1420",
        "updated_at": "2026-09-12T00:00:00Z",
    }
    after_comment = dict(base, updated_at="2026-09-12T01:00:00Z")
    first = module.build_finding(base, [], ["real_external_evidence"])
    second = module.build_finding(after_comment, [], ["real_external_evidence"])
    assert first.signature == second.signature


def test_approval_does_not_remove_external_evidence_requirement():
    issue = {
        "number": 1420,
        "title": "HUMANO: corpus real",
        "body": "corpus real e revisão humana",
        "html_url": "https://example.test/issues/1420",
        "updated_at": "2026-09-12T00:00:00Z",
    }
    comments = [{
        "body": "Aprovo o fluxo.",
        "author_association": "OWNER",
        "html_url": "https://example.test/issues/1420#issuecomment-1",
    }]
    finding = module.build_finding(issue, comments, ["real_external_evidence"])
    assert finding.approval_references
    assert "falta apenas comprovar o fato externo" in finding.decision


def test_scoped_gate_is_deferred_only_outside_its_target_scope():
    prod_issue = {"labels": [{"name": "satellite:defer-nonprod"}, {"name": "scope:prod-only"}]}
    ocr_issue = {"labels": [{"name": "satellite:defer-nonprod"}, {"name": "scope:ocr-certification-only"}]}
    assert module.should_defer_notification(prod_issue, "nonprod") is True
    assert module.should_defer_notification(prod_issue, "prod") is False
    assert module.should_defer_notification(prod_issue, "ocr-certification") is True
    assert module.should_defer_notification(ocr_issue, "nonprod") is True
    assert module.should_defer_notification(ocr_issue, "ocr-certification") is False
    assert module.should_defer_notification(ocr_issue, "prod") is True


def test_human_pending_workflow_defaults_schedule_to_nonprod_scope():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/human-pending-satellite.yml").read_text(encoding="utf-8")
    assert "default: nonprod" in workflow
    assert "- prod" in workflow
    assert "- ocr-certification" in workflow
    assert "--scope" in workflow


def test_human_pending_workflow_bootstraps_pytest_before_classifier():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/human-pending-satellite.yml").read_text(encoding="utf-8")
    setup_pos = workflow.index("actions/setup-python@v5")
    install_pos = workflow.index("python -m pip install --disable-pip-version-check pytest==9.0.3")
    test_pos = workflow.index("python -m pytest -q tests/test_human_pending_satellite.py")
    assert setup_pos < install_pos < test_pos
