"""
Serviço Gemini IA — free tier (gemini-1.5-flash).
Limites free tier: 15 req/min, 1.500 req/dia, 1M tokens/min.
Todos os erros são capturados e devolvidos como GeminiIndisponivel
para não derrubar o fluxo principal do ReqSys.
"""
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, date

logger = logging.getLogger('reqsys.gemini')

# ---------------------------------------------------------------------------
# Limites do free tier (gemini-1.5-flash)
# ---------------------------------------------------------------------------
_LIMITE_POR_MINUTO = 15
_LIMITE_POR_DIA = 1_500


class GeminiIndisponivel(Exception):
    """Lançada quando a API Gemini não pode ser usada (sem chave, quota, erro de rede)."""


# ---------------------------------------------------------------------------
# Tracker de uso — in-process, thread-safe, persiste enquanto o servidor vive
# ---------------------------------------------------------------------------
@dataclass
class _UsageTracker:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # timestamps dos últimos 60s (deque para eficiência)
    _janela_minuto: deque = field(default_factory=lambda: deque())
    # contador diário
    _dia_atual: date = field(default_factory=lambda: date.today())
    _total_dia: int = 0

    def registrar(self) -> None:
        agora = datetime.now(timezone.utc)
        hoje = agora.date()
        ts = agora.timestamp()

        with self._lock:
            # Vira o dia
            if hoje != self._dia_atual:
                self._dia_atual = hoje
                self._total_dia = 0
                self._janela_minuto.clear()

            # Remove registros fora da janela de 60s
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
                    'limite_por_minuto': _LIMITE_POR_MINUTO,
                    'limite_por_dia': _LIMITE_POR_DIA,
                    'restante_minuto': _LIMITE_POR_MINUTO,
                    'restante_dia': _LIMITE_POR_DIA,
                    'pct_dia_usado': 0.0,
                }

            limite_ts = ts - 60
            req_min = sum(1 for t in self._janela_minuto if t >= limite_ts)
            req_dia = self._total_dia

        restante_min = max(0, _LIMITE_POR_MINUTO - req_min)
        restante_dia = max(0, _LIMITE_POR_DIA - req_dia)
        pct = round((req_dia / _LIMITE_POR_DIA) * 100, 2)

        return {
            'req_ultimo_minuto': req_min,
            'req_hoje': req_dia,
            'limite_por_minuto': _LIMITE_POR_MINUTO,
            'limite_por_dia': _LIMITE_POR_DIA,
            'restante_minuto': restante_min,
            'restante_dia': restante_dia,
            'pct_dia_usado': pct,
        }


_tracker = _UsageTracker()


def get_uso() -> dict:
    """Retorna snapshot de uso da cota Gemini. Seguro para chamar a qualquer hora."""
    return _tracker.snapshot()


# ---------------------------------------------------------------------------
# Client Gemini
# ---------------------------------------------------------------------------
def _get_client(api_key: str, model: str):
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(model)
    except ImportError:
        raise GeminiIndisponivel('Pacote google-generativeai não instalado. Execute: pip install google-generativeai')


def _gerar(api_key: str, model: str, prompt: str) -> str:
    if not api_key:
        raise GeminiIndisponivel('GEMINI_API_KEY não configurada no .env')
    try:
        cliente = _get_client(api_key, model)
        resposta = cliente.generate_content(prompt)
        _tracker.registrar()
        return resposta.text.strip()
    except GeminiIndisponivel:
        raise
    except GeminiIndisponivel:
        raise
    except Exception as exc:
        msg = str(exc)
        msg_lower = msg.lower()
        # 429 = rate limit / quota — busca pelo código HTTP ou palavras-chave específicas
        # Evita falso positivo com 'rate' dentro de "generateContent"
        is_quota = (
            '429' in msg
            or 'resource_exhausted' in msg_lower
            or 'quota exceeded' in msg_lower
            or 'rate limit' in msg_lower
            or 'too many requests' in msg_lower
        )
        if is_quota:
            raise GeminiIndisponivel(
                f'Limite de requisições Gemini atingido (free tier: {_LIMITE_POR_MINUTO} req/min, '
                f'{_LIMITE_POR_DIA} req/dia). Tente novamente em alguns segundos.'
            )
        # 404 = modelo não encontrado / 400 = chave inválida
        is_bad_key = '400' in msg or 'api_key' in msg_lower or 'invalid' in msg_lower
        is_not_found = '404' in msg or 'not found' in msg_lower or 'not supported' in msg_lower
        if is_bad_key:
            raise GeminiIndisponivel('GEMINI_API_KEY inválida. Verifique a chave em aistudio.google.com.')
        if is_not_found:
            raise GeminiIndisponivel(
                f'Modelo "{model}" não disponível para esta chave. '
                'Verifique GEMINI_MODEL no .env. Modelos disponíveis: gemini-2.0-flash, gemini-2.5-flash.'
            )
        logger.exception('Erro inesperado ao chamar Gemini')
        raise GeminiIndisponivel(f'Gemini indisponível: {msg}')


# ---------------------------------------------------------------------------
# Funções de negócio
# ---------------------------------------------------------------------------
def resumir_requisito(titulo: str, descricao: str, api_key: str, model: str) -> str:
    prompt = (
        'Você é um analista de requisitos de software sênior. '
        'Resuma o requisito abaixo em no máximo 2 frases claras e objetivas, '
        'mantendo o contexto técnico e de negócio. Responda apenas o resumo, sem títulos ou marcadores.\n\n'
        f'Título: {titulo}\n'
        f'Descrição: {descricao}'
    )
    return _gerar(api_key, model, prompt)


def sugerir_descricao(titulo: str, area: str, sistema: str, api_key: str, model: str) -> str:
    prompt = (
        'Você é um analista de requisitos de software sênior. '
        'Com base no título, área e sistema informados, escreva uma descrição completa para este requisito. '
        'A descrição deve explicar a necessidade de negócio, o impacto esperado e critérios de aceite básicos. '
        'Máximo de 5 frases. Responda apenas a descrição, sem títulos ou marcadores.\n\n'
        f'Título: {titulo}\n'
        f'Área: {area or "não informada"}\n'
        f'Sistema: {sistema or "não informado"}'
    )
    return _gerar(api_key, model, prompt)


@dataclass
class ClassificacaoUrgencia:
    urgencia: str
    justificativa: str


def classificar_urgencia(titulo: str, descricao: str, api_key: str, model: str) -> ClassificacaoUrgencia:
    prompt = (
        'Você é um analista de requisitos de software sênior. '
        'Com base no título e descrição abaixo, classifique a urgência do requisito. '
        'Responda EXATAMENTE neste formato (duas linhas):\n'
        'URGENCIA: <baixa|media|alta|critica>\n'
        'JUSTIFICATIVA: <uma frase curta explicando o motivo>\n\n'
        f'Título: {titulo}\n'
        f'Descrição: {descricao}'
    )
    texto = _gerar(api_key, model, prompt)

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

    return ClassificacaoUrgencia(urgencia=urgencia, justificativa=justificativa)
