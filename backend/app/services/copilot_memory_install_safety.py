from __future__ import annotations

from typing import Any

from app.services.copilot_memory_install_assistant import listar_ambientes_instalacao

_PRODUCAO = {'production', 'prod', 'producao', 'produção'}


def _parece_producao(ambiente: dict[str, Any]) -> bool:
    valores = {
        str(ambiente.get('tipo') or '').strip().lower(),
        str(ambiente.get('nome') or '').strip().lower(),
    }
    if valores.intersection(_PRODUCAO):
        return True
    nome = str(ambiente.get('nome') or '').strip().lower()
    return nome.startswith('prod-') or nome.endswith('-prod') or ' produção' in nome or ' production' in nome


async def validar_destino_assistente(environment_id: str, environment_url: str) -> dict[str, Any]:
    """Relê o ambiente na Microsoft e bloqueia produção antes de qualquer implantação."""
    resultado = await listar_ambientes_instalacao()
    if resultado.get('erro'):
        raise ValueError(f"Nao foi possivel confirmar o ambiente Microsoft: {resultado['erro']}")

    ambiente = next(
        (item for item in resultado.get('ambientes', []) if str(item.get('id')) == str(environment_id)),
        None,
    )
    if ambiente is None:
        raise ValueError('Ambiente selecionado nao foi encontrado novamente na Microsoft')

    url_oficial = str(ambiente.get('url') or '').rstrip('/').lower()
    url_recebida = str(environment_url or '').rstrip('/').lower()
    if not url_oficial or url_oficial != url_recebida:
        raise ValueError('URL do ambiente diverge da fonte oficial Microsoft')
    if _parece_producao(ambiente):
        raise ValueError('O assistente Copilot Memory nao permite implantacao direta em producao')

    return ambiente
