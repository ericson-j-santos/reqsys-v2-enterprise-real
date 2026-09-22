"""Testes de caminhos críticos — increment gate governado."""

import json

import pytest

from app.services.increment_gate_service import (
    carregar_relatorio_coordenador,
    verificar_increment_gate,
)


def _escrever_relatorio(tmp_path, payload):
    path = tmp_path / "coordenador-status.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_increment_type_invalido_e_bloqueado():
    gate = verificar_increment_gate("tipo_inexistente")

    assert gate["permitido"] is False
    assert gate["motivo"] == "increment_type_invalido"


def test_strict_sem_relatorio_bloqueia(tmp_path, monkeypatch):
    inexistente = tmp_path / "ausente.json"
    monkeypatch.setenv("COORDENADOR_STATUS_JSON", str(inexistente))

    gate = verificar_increment_gate("gap_fix", strict=True)

    assert gate["permitido"] is False
    assert gate["motivo"] == "coordenador_status_ausente"


def test_increment_type_nao_permitido_no_relatorio(tmp_path, monkeypatch):
    relatorio = {
        "increment_gate": {
            "allowed_increment_types": ["hotfix"],
            "new_front_allowed": False,
            "blockers": ["state_yellow"],
        },
        "automatic_backlog": [],
    }
    path = _escrever_relatorio(tmp_path, relatorio)
    monkeypatch.setenv("COORDENADOR_STATUS_JSON", str(path))

    gate = verificar_increment_gate("new_front", strict=True)

    assert gate["permitido"] is False
    assert gate["motivo"] == "increment_type_nao_permitido"
    assert "state_yellow" in gate["detalhe"]


def test_nova_frente_bloqueada_quando_coordenador_desabilita(tmp_path, monkeypatch):
    relatorio = {
        "increment_gate": {
            "allowed_increment_types": ["new_front", "gap_fix"],
            "new_front_allowed": False,
            "blockers": ["state_yellow"],
        },
        "automatic_backlog": [],
    }
    path = _escrever_relatorio(tmp_path, relatorio)
    monkeypatch.setenv("COORDENADOR_STATUS_JSON", str(path))

    gate = verificar_increment_gate("new_front", strict=True)

    assert gate["permitido"] is False
    assert gate["motivo"] == "nova_frente_bloqueada"


def test_gap_fix_invalido_quando_referencia_ausente_no_backlog(tmp_path, monkeypatch):
    relatorio = {
        "increment_gate": {
            "allowed_increment_types": ["gap_fix"],
            "new_front_allowed": False,
            "blockers": [],
        },
        "automatic_backlog": [{"id": "OPS-GAP-100"}],
    }
    path = _escrever_relatorio(tmp_path, relatorio)
    monkeypatch.setenv("COORDENADOR_STATUS_JSON", str(path))

    gate = verificar_increment_gate("gap_fix", "OPS-GAP-999", strict=True)

    assert gate["permitido"] is False
    assert gate["motivo"] == "gap_fix_invalido"


def test_incremento_permitido_com_relatorio_governado(tmp_path, monkeypatch):
    relatorio = {
        "increment_gate": {
            "allowed_increment_types": ["gap_fix", "hotfix"],
            "new_front_allowed": False,
            "blockers": [],
        },
        "automatic_backlog": [{"id": "OPS-GAP-200"}],
    }
    path = _escrever_relatorio(tmp_path, relatorio)
    monkeypatch.setenv("COORDENADOR_STATUS_JSON", str(path))

    gate = verificar_increment_gate("gap_fix", "OPS-GAP-200", strict=True)

    assert gate["permitido"] is True
    assert gate["motivo"] == "incremento_permitido"


def test_carregar_relatorio_coordenador_via_env(tmp_path, monkeypatch):
    relatorio = {"increment_gate": {"allowed_increment_types": ["hotfix"]}}
    path = _escrever_relatorio(tmp_path, relatorio)
    monkeypatch.setenv("COORDENADOR_STATUS_JSON", str(path))

    carregado = carregar_relatorio_coordenador(strict=True)

    assert carregado == relatorio


@pytest.mark.parametrize("increment_type", ["gap_fix", "hotfix", "consolidate", "close_duplicate"])
def test_relatorio_permissivo_aprova_tipos_validos(increment_type):
    gate = verificar_increment_gate(increment_type)

    assert gate["permitido"] is True


def test_salvar_vinculos_pr_merged_atualiza_requisito():
    from app.db import SessionLocal
    from app.models.requisito import Requisito
    from app.services.webhook_processor import salvar_vinculos

    db = SessionLocal()
    codigo = "REQ-CRITICAL-999"
    try:
        requisito = Requisito(
            codigo=codigo,
            titulo="Requisito webhook crítico",
            descricao="Cobertura do caminho pr_merged",
            area="TI",
            sistema="ReqSys",
            solicitante="pytest",
            status="em_desenvolvimento",
        )
        db.add(requisito)
        db.commit()

        ids = salvar_vinculos(
            db,
            [
                {
                    "requisito_codigo": codigo,
                    "tipo": "pr",
                    "provedor": "github",
                    "repo": "owner/repo",
                    "referencia": "42",
                    "pr_merged": True,
                    "autor": "dev",
                }
            ],
        )

        assert len(ids) == 1
        atualizado = db.query(Requisito).filter(Requisito.codigo == codigo).first()
        assert atualizado is not None
        assert atualizado.status == "implementado"
    finally:
        db.query(Requisito).filter(Requisito.codigo == codigo).delete()
        db.commit()
        db.close()
