from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings

REGISTRY_PATH = Path(__file__).resolve().parents[3] / 'config' / 'external-sources-registry.json'


@dataclass(frozen=True)
class FonteExternaRegistrada:
    id: str
    nome: str
    origem: str
    ttl_minutos: int
    confiabilidade: str
    autorizado: bool
    mock_as_real: bool
    expirada: bool
    coletado_em: str


def _agora() -> datetime:
    return datetime.now(UTC)


def carregar_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {'schema_version': '1.0.0', 'policy': {'allow_mock_in_production': False}, 'sources': []}
    with REGISTRY_PATH.open('r', encoding='utf-8') as handle:
        return json.load(handle)


def validar_registry_producao() -> None:
    if not settings.is_production:
        return
    registry = carregar_registry()
    policy = registry.get('policy') or {}
    if policy.get('allow_mock_in_production'):
        raise RuntimeError('Registry de fontes externas: allow_mock_in_production=true bloqueado em producao')
    for source in registry.get('sources') or []:
        if source.get('mock_as_real'):
            raise RuntimeError(
                f"Fonte externa '{source.get('id')}' marcada como mock_as_real=true bloqueada em producao"
            )


def _fonte_expirada(source: dict[str, Any], coletado_em: datetime, agora: datetime) -> bool:
    ttl = int(source.get('ttlMinutos') or registry_default_ttl())
    limite = coletado_em + timedelta(minutes=ttl)
    return agora > limite


def registry_default_ttl() -> int:
    registry = carregar_registry()
    return int((registry.get('policy') or {}).get('default_ttl_minutes') or 1440)


def listar_fontes_externas(coletado_em: datetime | None = None) -> list[FonteExternaRegistrada]:
    agora = coletado_em or _agora()
    coletado_iso = agora.isoformat()
    registry = carregar_registry()
    fontes: list[FonteExternaRegistrada] = []
    for source in registry.get('sources') or []:
        ttl = int(source.get('ttlMinutos') or registry_default_ttl())
        expirada = _fonte_expirada(source, agora, agora)
        fontes.append(
            FonteExternaRegistrada(
                id=str(source.get('id') or ''),
                nome=str(source.get('nome') or ''),
                origem=str(source.get('origem') or ''),
                ttl_minutos=ttl,
                confiabilidade=str(source.get('confiabilidade') or 'baixa'),
                autorizado=bool(source.get('autorizado')),
                mock_as_real=bool(source.get('mock_as_real')),
                expirada=expirada,
                coletado_em=coletado_iso,
            )
        )
    return fontes


def resumo_fontes_externas(coletado_em: datetime | None = None) -> dict[str, Any]:
    fontes = listar_fontes_externas(coletado_em)
    autorizadas = [fonte for fonte in fontes if fonte.autorizado and not fonte.mock_as_real and not fonte.expirada]
    return {
        'total': len(fontes),
        'autorizadas_validas': len(autorizadas),
        'expiradas': sum(1 for fonte in fontes if fonte.expirada),
        'mock_marcadas': sum(1 for fonte in fontes if fonte.mock_as_real),
        'pendentes_auditoria': sum(1 for fonte in fontes if not fonte.autorizado),
    }
