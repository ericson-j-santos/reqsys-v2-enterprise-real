"""
Serviço Gemini IA — free tier (gemini-1.5-flash).
Limites: 15 req/min, 1.500 req/dia, 1M tokens/min.
Todos os erros são capturados e devolvidos como GeminiIndisponivel
para não derrubar o fluxo principal do ReqSys.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger('reqsys.gemini')


class GeminiIndisponivel(Exception):
    """Lançada quando a API Gemini não pode ser usada (sem chave, quota, erro de rede)."""


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
        return resposta.text.strip()
    except GeminiIndisponivel:
        raise
    except Exception as exc:
        msg = str(exc)
        if '429' in msg or 'quota' in msg.lower() or 'rate' in msg.lower():
            raise GeminiIndisponivel('Limite de requisições Gemini atingido (free tier: 15 req/min). Tente novamente em alguns segundos.')
        if '400' in msg or 'api_key' in msg.lower() or 'invalid' in msg.lower():
            raise GeminiIndisponivel('GEMINI_API_KEY inválida. Verifique a chave em aistudio.google.com.')
        logger.exception('Erro inesperado ao chamar Gemini')
        raise GeminiIndisponivel(f'Gemini indisponível: {msg}')


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
