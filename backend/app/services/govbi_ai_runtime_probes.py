from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Any

from app.services.gemini import GeminiIndisponivel, resumir_requisito


@dataclass(frozen=True)
class ProviderProbeConfig:
    provider: str
    configurado: bool
    papel: str
    chave_presente: bool
    modelo: str


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _probe_nao_configurado(config: ProviderProbeConfig) -> dict[str, Any]:
    return {
        'provider': config.provider,
        'papel': config.papel,
        'modelo': config.modelo,
        'status': 'skipped',
        'motivo': 'provider_nao_configurado',
        'latencia_ms': None,
        'executado_em': _agora_iso(),
        'seguranca': {
            'sem_prompt_em_resposta': True,
            'sem_resposta_modelo_em_resposta': True,
            'sem_chave_exposta': True,
        },
    }


def _normalizar_provider_usado(provider_usado: str) -> str:
    return (provider_usado or 'desconhecido').strip().lower() or 'desconhecido'


def executar_runtime_probes_govbi(
    *,
    gemini_api_key: str,
    gemini_model: str,
    groq_api_key: str,
    groq_model: str,
    executor: Callable[..., tuple[str, str]] = resumir_requisito,
) -> dict[str, Any]:
    """
    Executa probes reais e controlados de runtime para GovBI IA.

    O retorno nunca inclui prompt, resposta completa do modelo, chaves ou PII.
    Quando Gemini falha e Groq está configurado, o executor existente pode acionar fallback.
    """
    configs = [
        ProviderProbeConfig(
            provider='gemini',
            configurado=bool(gemini_api_key),
            papel='primario',
            chave_presente=bool(gemini_api_key),
            modelo=gemini_model,
        ),
        ProviderProbeConfig(
            provider='groq',
            configurado=bool(groq_api_key),
            papel='fallback',
            chave_presente=bool(groq_api_key),
            modelo=groq_model,
        ),
    ]

    probes: list[dict[str, Any]] = []
    inicio = time.perf_counter()

    if not gemini_api_key and not groq_api_key:
        probes = [_probe_nao_configurado(config) for config in configs]
    else:
        started = time.perf_counter()
        try:
            _, provider_usado = executor(
                titulo='Smoke test operacional GovBI IA',
                descricao='Validar disponibilidade runtime de provider LLM sem trafegar dados sensiveis.',
                api_key=gemini_api_key,
                model=gemini_model,
                groq_key=groq_api_key,
                groq_model=groq_model,
            )
            provider_usado = _normalizar_provider_usado(provider_usado)
            latency = round((time.perf_counter() - started) * 1000, 2)
            probes.append({
                'provider': provider_usado,
                'papel': 'primario' if provider_usado == 'gemini' else 'fallback',
                'status': 'success',
                'latencia_ms': latency,
                'executado_em': _agora_iso(),
                'fallback_acionado': provider_usado == 'groq',
                'seguranca': {
                    'sem_prompt_em_resposta': True,
                    'sem_resposta_modelo_em_resposta': True,
                    'sem_chave_exposta': True,
                },
            })
        except GeminiIndisponivel as exc:
            latency = round((time.perf_counter() - started) * 1000, 2)
            probes.append({
                'provider': 'llm',
                'papel': 'primario_ou_fallback',
                'status': 'failure',
                'tipo_erro': 'provider_indisponivel',
                'mensagem_sanitizada': str(exc)[:180],
                'latencia_ms': latency,
                'executado_em': _agora_iso(),
                'fallback_acionado': bool(groq_api_key),
                'seguranca': {
                    'sem_prompt_em_resposta': True,
                    'sem_resposta_modelo_em_resposta': True,
                    'sem_chave_exposta': True,
                },
            })

        for config in configs:
            if not config.configurado:
                probes.append(_probe_nao_configurado(config))

    falhas = [probe for probe in probes if probe['status'] == 'failure']
    sucessos = [probe for probe in probes if probe['status'] == 'success']
    skipped = [probe for probe in probes if probe['status'] == 'skipped']
    status_geral = 'verde' if sucessos and not falhas else 'amarelo' if sucessos and falhas else 'vermelho'
    if skipped and not sucessos and not falhas:
        status_geral = 'amarelo'

    return {
        'produto': 'GovBI IA / ReqSys',
        'status_geral': status_geral,
        'executado_em': _agora_iso(),
        'duracao_total_ms': round((time.perf_counter() - inicio) * 1000, 2),
        'probes': probes,
        'resumo': {
            'total': len(probes),
            'sucessos': len(sucessos),
            'falhas': len(falhas),
            'ignorados': len(skipped),
            'fallback_acionado': any(probe.get('fallback_acionado') for probe in probes),
        },
        'seguranca': {
            'sem_prompt_em_resposta': True,
            'sem_resposta_modelo_em_resposta': True,
            'sem_chave_exposta': True,
            'sem_pii': True,
        },
    }
