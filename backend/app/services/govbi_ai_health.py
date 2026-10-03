from __future__ import annotations

from typing import Any


def _status_provider(configurado: bool, cota: dict[str, Any]) -> str:
    if not configurado:
        return 'nao_configurado'
    restante_dia = cota.get('restante_dia')
    if isinstance(restante_dia, (int, float)) and restante_dia <= 0:
        return 'quota_esgotada'
    return 'operacional'


def _percentual_estimado(
    gemini_ok: bool,
    groq_ok: bool,
    possui_telemetry: bool,
    persistencia_ativa: bool,
    ultimo_probe_ok: bool,
) -> int:
    percentual = 45
    if gemini_ok:
        percentual += 25
    if groq_ok:
        percentual += 10
    if gemini_ok and groq_ok:
        percentual += 5
    if possui_telemetry:
        percentual += 5
    if persistencia_ativa:
        percentual += 5
    if ultimo_probe_ok:
        percentual += 5
    return min(percentual, 100)


def montar_govbi_ai_health(
    *,
    gemini_configurado: bool,
    gemini_modelo: str,
    gemini_cota: dict[str, Any],
    groq_configurado: bool,
    groq_modelo: str,
    groq_cota: dict[str, Any],
    telemetry: dict[str, Any],
    telemetry_persistida: dict[str, Any] | None = None,
    ultimo_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta status operacional do GovBI IA sem expor chaves, prompts ou respostas."""
    fallback_ativo = gemini_configurado and groq_configurado
    possui_telemetry = any(
        dados.get('total_requisicoes', 0) > 0
        for dados in telemetry.values()
        if isinstance(dados, dict)
    )
    persistencia_ativa = bool((telemetry_persistida or {}).get('store', {}).get('existe'))
    ultimo_probe_ok = (ultimo_probe or {}).get('status_geral') == 'verde'

    if fallback_ativo and (ultimo_probe_ok or possui_telemetry):
        status_geral = 'verde'
        diagnostico = 'GovBI IA com provider primario, fallback, telemetry e evidência runtime operacional.'
    elif fallback_ativo:
        status_geral = 'amarelo'
        diagnostico = 'GovBI IA configurado com fallback, aguardando execução de probe/runtime para evidência operacional.'
    elif gemini_configurado or groq_configurado:
        status_geral = 'amarelo'
        diagnostico = 'GovBI IA operacional em modo parcial; fallback ou provider primario pendente.'
    else:
        status_geral = 'vermelho'
        diagnostico = 'GovBI IA sem provider LLM configurado.'

    passos_pendentes: list[dict[str, str]] = []
    if not gemini_configurado:
        passos_pendentes.append({
            'passo': 'Configurar GEMINI_API_KEY',
            'prioridade': 'alta',
            'motivo': 'Gemini e o provider primario gratuito previsto para o GovBI IA.',
        })
    if not groq_configurado:
        passos_pendentes.append({
            'passo': 'Configurar GROQ_API_KEY',
            'prioridade': 'media',
            'motivo': 'Ativa fallback gratuito governado quando Gemini falhar ou atingir quota.',
        })
    if not possui_telemetry:
        passos_pendentes.append({
            'passo': 'Executar smoke test IA',
            'prioridade': 'media',
            'motivo': 'Necessario evidenciar chamada real ou mockada para popular telemetry operacional.',
        })
    if not persistencia_ativa:
        passos_pendentes.append({
            'passo': 'Popular storage de telemetry',
            'prioridade': 'media',
            'motivo': 'Historico governado ainda nao possui eventos persistidos.',
        })
    if not ultimo_probe_ok:
        passos_pendentes.append({
            'passo': 'Executar POST /v1/ia/govbi/probes',
            'prioridade': 'media',
            'motivo': 'Necessario validar latencia, disponibilidade e fallback em runtime.',
        })

    return {
        'produto': 'GovBI IA / ReqSys',
        'status_geral': status_geral,
        'percentual_operacional_estimado': _percentual_estimado(
            gemini_configurado,
            groq_configurado,
            possui_telemetry,
            persistencia_ativa,
            ultimo_probe_ok,
        ),
        'diagnostico': diagnostico,
        'gemini_gratuito_configurado': gemini_configurado,
        'fallback_ativo': fallback_ativo,
        'seguranca': {
            'sem_chaves_expostas': True,
            'sem_prompt_em_telemetry': True,
            'sem_resposta_em_telemetry': True,
        },
        'provedores': {
            'gemini': {
                'papel': 'primario',
                'configurado': gemini_configurado,
                'modelo': gemini_modelo,
                'status': _status_provider(gemini_configurado, gemini_cota),
                'cota': gemini_cota,
            },
            'groq': {
                'papel': 'fallback',
                'configurado': groq_configurado,
                'modelo': groq_modelo,
                'status': _status_provider(groq_configurado, groq_cota),
                'cota': groq_cota,
            },
        },
        'telemetry': telemetry,
        'telemetry_persistida': telemetry_persistida or {},
        'ultimo_probe': ultimo_probe or {},
        'smoke_tests_recomendados': [
            'GET /v1/ia/status',
            'GET /v1/ia/govbi/health',
            'GET /v1/ia/govbi/telemetry',
            'POST /v1/ia/govbi/probes',
        ],
        'passos_pendentes': passos_pendentes,
    }
