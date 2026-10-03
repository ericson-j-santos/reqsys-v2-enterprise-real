from __future__ import annotations

import json
from pathlib import Path

from scripts import padrao_ouro_scorecard as scorecard


def _audit_report():
    return {
        "schema_version": "1.1.0",
        "source": "prod-readiness-audit",
        "validated_at": "2026-07-05T00:00:00Z",
        "checks": [
            {
                "id": "auth_demo_disabled",
                "area": "security",
                "status": "ok",
                "human_required": False,
                "detail": "Produção exige demo desabilitado.",
            },
            {
                "id": "azure_public_config",
                "area": "auth_azure",
                "status": "ok",
                "human_required": False,
                "detail": "Azure configurado.",
            },
            {
                "id": "public_smoke",
                "area": "runtime",
                "status": "ok",
                "human_required": False,
                "detail": "Smoke público ok.",
            },
            {
                "id": "fly_secrets_reviewed",
                "area": "secrets",
                "status": "manual",
                "human_required": True,
                "detail": "Revisão humana pendente.",
            },
            {
                "id": "governance_approvals",
                "area": "governance",
                "status": "action_required",
                "human_required": True,
                "detail": "Aprovação pendente.",
            },
            {
                "id": "corporate_domain",
                "area": "dns",
                "status": "recommended",
                "human_required": True,
                "detail": "Domínio corporativo recomendado.",
            },
        ],
    }


def test_build_scorecard_consolida_dominios_e_risco():
    result = scorecard.build_scorecard(_audit_report())

    assert result["schema_version"] == "1.0.0"
    assert result["source"] == "padrao-ouro-scorecard"
    assert result["maturity_percent"] < 100
    assert result["risk"]["level"] == "medium"
    assert "governance" in result["attention_domains"]
    assert result["recommended_next_increment"]["domain"] in {"governance", "secrets"}


def test_build_scorecard_bloqueia_quando_dominio_obrigatorio_falha():
    audit = _audit_report()
    audit["checks"][0]["status"] = "blocked"

    result = scorecard.build_scorecard(audit)

    assert result["status"] == "blocked"
    assert result["risk"]["level"] == "high"
    assert "security" in result["blocked_domains"]


def test_dominios_sem_check_geram_lacuna_manual_ou_action_required():
    result = scorecard.build_scorecard({"source": "empty", "checks": []})
    domains = {item["domain"]: item for item in result["domains"]}

    assert domains["security"]["status"] == "action_required"
    assert domains["documentation"]["status"] == "manual"
    assert result["risk"]["confidence"] == "medium"


def test_main_gera_json_e_markdown(tmp_path: Path):
    audit = tmp_path / "audit.json"
    output = tmp_path / "scorecard.json"
    markdown = tmp_path / "scorecard.md"
    audit.write_text(json.dumps(_audit_report()), encoding="utf-8")

    code = scorecard.main([
        "--input",
        str(audit),
        "--output",
        str(output),
        "--markdown-output",
        str(markdown),
    ])

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source"] == "padrao-ouro-scorecard"
    assert "Scorecard Executivo" in markdown.read_text(encoding="utf-8")


def test_strict_falha_quando_scorecard_esta_bloqueado(tmp_path: Path):
    audit_payload = _audit_report()
    audit_payload["checks"][0]["status"] = "blocked"
    audit = tmp_path / "audit.json"
    output = tmp_path / "scorecard.json"
    audit.write_text(json.dumps(audit_payload), encoding="utf-8")

    code = scorecard.main(["--input", str(audit), "--output", str(output), "--strict"])

    assert code == 1
