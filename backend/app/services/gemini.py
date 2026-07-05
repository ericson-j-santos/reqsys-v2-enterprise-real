"""
Serviço IA — Gemini (primary) + Groq/Llama (fallback automático).

A chamada externa passa pela porta comum `LLMGateway`.
O serviço mantém apenas regras específicas da IA Assistente: cota, fallback
Gemini -> Groq e normalização de exceções para a API existente.
"""
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.services.llm_provider import LLMGateway
from app.services.llm_provider import _post_json as _llm_post_json

logger = logging.getLogger('reqsys.ia')

# ---------------------------------------------------------------------------
# Limites free tier
# ---------------------------------------------------------------------------
_GEMINI_LIMITE_MIN = 15
_GEMINI_LIMITE_DIA = 1_500
_GROQ_LIMITE_MIN = 30
_GROQ_LIMITE_DIA = 14_400


class GeminiIndisponivel(Exception):
    """Lançada quando nenhum provider IA está disponível."""


# ---------------------------------------------------------------------------
# Tracker de uso — in-process, thread-safe, persiste enquanto o servidor vive
# ---------------------------------------------------------------------------
@dataclass
class _UsageTracker:
    limite_por_minuto: int = 15
    limite_por_dia: int = 1_500
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _janela_minuto: deque = field(default_factory=lambda: deque())
    _dia_atual: date = field(default_factory=lambda: date.today())
    _total_dia: int = 0

    def registrar(self) -> None:
        agora = datetime.now(timezone.utc)
        hoje = agora.date()
        ts = agora.timestamp()
        with self._lock:
            if hoje != self._dia_atual:
                self._dia_atual = hoje
                self._total_dia = 0
                self._janela_minuto.clear()
            limite_ts = ts - 60
            while self._janela_minuto and self._janela_minuto[0] < limite_ts:
                self._janela_minuto.popleft()
            self._janela_minuto.append(ts)
            self._total_dia += 1

    def snapshot(self) -> dict:
        agora = datetime.now(timezone.utc)
        hoje = agora.date()
        ts = agora.timestamp()
        with self._lock:
            if hoje != self._dia_atual:
                return {
                    'req_ultimo_minuto': 0,
                    'req_hoje': 0,
                    'limite_por_minuto': self.limite_por_minuto,
                    'limite_por_dia': self.limite_por_dia,
                    'restante_minuto': self.limite_por_minuto,
                    'restante_dia': self.limite_por_dia,
                    'pct_dia_usado': 0.0,
                }
            limite_ts = ts - 60
            req_min = sum(1 for t in self._janela_minuto if t >= limite_ts)
            req_dia = self._total_dia
        restante_min = max(0, self.limite_por_minuto - req_min)
        restante_dia = max(0, self.limite_por_dia - req_dia)
        pct = round((req_dia / self.limite_por_dia) * 100, 2)
        return {
            'req_ultimo_minuto': req_min,
            'req_hoje': req_dia,
            'limite_por_minuto': self.limite_por_minuto,
            'limite_por_dia': self.limite_por_dia,
            'restante_minuto': restante_min,
            'restante_dia': restante_dia,
            'pct_dia_usado': pct,
        }


_gemini_tracker = _UsageTracker(limite_por_minuto=_GEMINI_LIMITE_MIN, limite_por_dia=_GEMINI_LIMITE_DIA)
_groq_tracker = _UsageTracker(limite_por_minuto=_GROQ_LIMITE_MIN, limite_por_dia=_GROQ_LIMITE_DIA)


def get_uso() -> dict:
    """Snapshot de uso Gemini."""
    return _gemini_tracker.snapshot()


def get_uso_groq() -> dict:
    """Snapshot de uso Groq."""
    return _groq_tracker.snapshot()


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None, timeout: int = 45) -> dict:
    return _llm_post_json(url, payload, headers, timeout)


def _gateway() -> LLMGateway:
    return LLMGateway(post_json=_post_json)


def _is_quota_error(msg: str) -> bool:
    msg_lower = msg.lower()
    return (
        '429' in msg
        or 'resource_exhausted' in msg_lower
        or 'quota exceeded' in msg_lower
        or 'rate_limit_exceeded' in msg_lower
        or 'rate limit' in msg_lower
        or 'too many requests' in msg_lower
    )


def _is_bad_key_error(msg: str) -> bool:
    msg_lower = msg.lower()
    return (
        '400' in msg
        or '401' in msg
        or 'api_key' in msg_lower
        or 'invalid api key' in msg_lower
        or 'authentication' in msg_lower
        or 'invalid' in msg_lower
    )


def _is_model_error(msg: str) -> bool:
    msg_lower = msg.lower()
    return '404' in msg or 'not found' in msg_lower or 'not supported' in msg_lower


# ---------------------------------------------------------------------------
# Client Gemini via porta comum
# ---------------------------------------------------------------------------
def _gerar(api_key: str, model: str, prompt: str) -> str:
    if not api_key:
        raise GeminiIndisponivel('GEMINI_API_KEY não configurada no .env')
    try:
        texto = _gateway().gerar_gemini(
            api_key=api_key,
            model=model,
            prompt=prompt,
        )
        _gemini_tracker.registrar()
        return texto.strip()
    except GeminiIndisponivel:
        raise
    except Exception as exc:
        msg = str(exc)
        if _is_quota_error(msg):
            raise GeminiIndisponivel(
                f'Quota Gemini esgotada (free tier: {_GEMINI_LIMITE_MIN} req/min, '
                f'{_GEMINI_LIMITE_DIA} req/dia). Ativando fallback Groq...'
            )
        if _is_bad_key_error(msg):
            raise GeminiIndisponivel('GEMINI_API_KEY inválida. Verifique a chave em aistudio.google.com.')
        if _is_model_error(msg):
            raise GeminiIndisponivel(
                f'Modelo Gemini "{model}" não disponível. '
                'Modelos válidos: gemini-2.0-flash, gemini-2.5-flash.'
            )
        logger.exception('Erro inesperado ao chamar Gemini')
        raise GeminiIndisponivel(f'Gemini indisponível: {msg}')


# ---------------------------------------------------------------------------
# Client Groq via porta comum
# ---------------------------------------------------------------------------
def _gerar_groq(api_key: str, model: str, prompt: str) -> str:
    if not api_key:
        raise GeminiIndisponivel('GROQ_API_KEY não configurada no .env')
    try:
        texto = _gateway().gerar_groq(
            api_key=api_key,
            model=model,
            prompt=prompt,
        )
        _groq_tracker.registrar()
        return texto.strip()
    except GeminiIndisponivel:
        raise
    except Exception as exc:
        msg = str(exc)
        if _is_quota_error(msg):
            raise GeminiIndisponivel(
                f'Quota Groq esgotada (free tier: {_GROQ_LIMITE_MIN} req/min, '
                f'{_GROQ_LIMITE_DIA} req/dia). Tente novamente em instantes.'
            )
        if _is_bad_key_error(msg):
            raise GeminiIndisponivel('GROQ_API_KEY inválida. Verifique a chave em console.groq.com.')
        logger.exception('Erro inesperado ao chamar Groq')
        raise GeminiIndisponivel(f'Groq indisponível: {msg}')


# ---------------------------------------------------------------------------
# Orquestrador com fallback
# ---------------------------------------------------------------------------
def _gerar_com_fallback(
    gemini_key: str, gemini_model: str,
    groq_key: str, groq_model: str,
    prompt: str,
) -> tuple[str, str]:
    """Tenta Gemini; se indisponível e groq_key configurada, usa Groq. Retorna (texto, provedor)."""
    try:
        return _gerar(gemini_key, gemini_model, prompt), 'gemini'
    except GeminiIndisponivel as exc:
        if groq_key:
            logger.info('Gemini indisponível (%s) — usando Groq como fallback.', exc)
            return _gerar_groq(groq_key, groq_model, prompt), 'groq'
        raise


# ---------------------------------------------------------------------------
# Funções de negócio — retornam (resultado, provedor_usado)
# ---------------------------------------------------------------------------
def resumir_requisito(
    titulo: str, descricao: str,
    api_key: str, model: str,
    groq_key: str = '', groq_model: str = '',
) -> tuple[str, str]:
    prompt = (
        'Você é um analista de requisitos de software sênior. '
        'Resuma o requisito abaixo em no máximo 2 frases claras e objetivas, '
        'mantendo o contexto técnico e de negócio. Responda apenas o resumo, sem títulos ou marcadores.\n\n'
        f'Título: {titulo}\n'
        f'Descrição: {descricao}'
    )
    return _gerar_com_fallback(api_key, model, groq_key, groq_model, prompt)


def sugerir_descricao(
    titulo: str, area: str, sistema: str,
    api_key: str, model: str,
    groq_key: str = '', groq_model: str = '',
) -> tuple[str, str]:
    prompt = (
        'Você é um analista de requisitos de software sênior. '
        'Com base no título, área e sistema informados, escreva uma descrição completa para este requisito. '
        'A descrição deve explicar a necessidade de negócio, o impacto esperado e critérios de aceite básicos. '
        'Máximo de 5 frases. Responda apenas a descrição, sem títulos ou marcadores.\n\n'
        f'Título: {titulo}\n'
        f'Área: {area or "não informada"}\n'
        f'Sistema: {sistema or "não informado"}'
    )
    return _gerar_com_fallback(api_key, model, groq_key, groq_model, prompt)


@dataclass
class ClassificacaoUrgencia:
    urgencia: str
    justificativa: str


def classificar_urgencia(
    titulo: str, descricao: str,
    api_key: str, model: str,
    groq_key: str = '', groq_model: str = '',
) -> tuple[ClassificacaoUrgencia, str]:
    prompt = (
        'Você é um analista de requisitos de software sênior. '
        'Com base no título e descrição abaixo, classifique a urgência do requisito. '
        'Responda EXATAMENTE neste formato (duas linhas):\n'
        'URGENCIA: <baixa|media|alta|critica>\n'
        'JUSTIFICATIVA: <uma frase curta explicando o motivo>\n\n'
        f'Título: {titulo}\n'
        f'Descrição: {descricao}'
    )
    texto, provedor = _gerar_com_fallback(api_key, model, groq_key, groq_model, prompt)

    urgencia = 'media'
    justificativa = texto

    for linha in texto.splitlines():
        linha_lower = linha.lower()
        if linha_lower.startswith('urgencia:') or linha_lower.startswith('urgência:'):
            valor = linha.split(':', 1)[1].strip().lower()
            if valor in ('baixa', 'media', 'média', 'alta', 'critica', 'crítica'):
                urgencia = valor.replace('média', 'media').replace('crítica', 'critica')
        elif linha_lower.startswith('justificativa:'):
            justificativa = linha.split(':', 1)[1].strip()

    return ClassificacaoUrgencia(urgencia=urgencia, justificativa=justificativa), provedor
