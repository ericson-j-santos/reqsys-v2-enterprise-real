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
