from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import requests

from app.core.config import settings

logger = logging.getLogger('reqsys.codex_governado')
audit_logger = logging.getLogger('reqsys.audit.codex_governado')

Provider = Literal['mock', 'ollama', 'openai', 'claude']

_PADROES_SENSIVEIS = [
    re.compile(r'(senha|password|passwd)\s*[:=]', re.I),
    re.compile(r'(api[_-]?key|access[_-]?key|private[_-]?key)\s*[:=]', re.I),
    re.compile(r'(authorization|bearer)\s+', re.I),
    re.compile(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b'),
]

_SYSTEM_PROMPT = (
    'Atue como arquiteto senior do ReqSys. Responda em portugues do Brasil, '
    'com decisao objetiva, riscos, implementacao minima segura, validacao, '
    'testes e payload rastreavel para ReqSys. Nao invente evidencias.'
)


@dataclass
class RateLimitState:
    janela_segundos: int = 60
    limite: int = 20
    acessos: dict[str, list[float]] = field(default_factory=dict)

    def consumir(self, chave: str) -> tuple[bool, int]:
        agora = time.time()
        inicio = agora - self.janela_segundos
        eventos = [t for t in self.acessos.get(chave, []) if t >= inicio]
        if len(eventos) >= self.limite:
            restante = max(1, int(self.janela_segundos - (agora - eventos[0])))
            self.acessos[chave] = eventos
            return False, restante
        eventos.append(agora)
        self.acessos[chave] = eventos
        return True, 0


rate_limit_state = RateLimitState()


def gerar_correlation_id(valor: str | None = None) -> str:
    if valor and valor.strip():
        return valor.strip()[:120]
    return f'codex-{uuid.uuid4().hex[:16]}'


def gerar_fingerprint(texto: str) -> str:
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()[:16]


def validar_conteudo_seguro(textos: list[str]) -> list[str]:
    bruto = '\n'.join(textos)
    achados: list[str] = []
    for padrao in _PADROES_SENSIVEIS:
        if padrao.search(bruto):
            achados.append(padrao.pattern)
    return achados


def montar_prompt(contexto: str, entrada: str) -> str:
    return (
        f'{_SYSTEM_PROMPT}\n\n'
        f'Contexto tecnico:\n{contexto}\n\n'
        f'Entrada para analise:\n{entrada}\n\n'
        'Retorne: resumo executivo, decisao recomendada, riscos, passos de implementacao, testes e payload ReqSys.'
    )


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 45) -> dict[str, Any]:
    resposta = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
    resposta.raise_for_status()
    return resposta.json()


def chamar_ollama(prompt: str) -> str:
    base_url = (settings.codex_ollama_base_url or 'http://localhost:11434').rstrip('/')
    payload = {
        'model': settings.codex_ollama_model,
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.1},
    }
    data = _post_json(f'{base_url}/api/generate', payload)
    return str(data.get('response') or '')


def chamar_openai(prompt: str) -> str:
    if not settings.codex_openai_key:
        raise RuntimeError('CODEX_OPENAI_KEY ausente')
    payload = {
        'model': settings.codex_openai_model,
        'messages': [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.1,
    }
    headers = {'Authorization': f'Bearer {settings.codex_openai_key}', 'Content-Type': 'application/json'}
    data = _post_json('https://api.openai.com/v1/chat/completions', payload, headers=headers)
    return str(data['choices'][0]['message']['content'])


def chamar_claude(prompt: str) -> str:
    if not settings.codex_claude_key:
        raise RuntimeError('CODEX_CLAUDE_KEY ausente')
    payload = {
        'model': settings.codex_claude_model,
        'max_tokens': 1600,
        'temperature': 0.1,
        'system': _SYSTEM_PROMPT,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    headers = {
        'x-api-key': settings.codex_claude_key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    }
    data = _post_json('https://api.anthropic.com/v1/messages', payload, headers=headers)
    blocos = data.get('content') or []
    return '\n'.join(str(item.get('text') or '') for item in blocos if isinstance(item, dict))


def resposta_mock(contexto: str, entrada: str, correlation_id: str) -> str:
    return json.dumps({
        'resumo': 'Analise governada executada em modo mock para validacao operacional.',
        'decisao': 'Usar backend autenticado como ponte segura entre GitHub Pages, provedores de IA e ReqSys.',
        'riscos': ['credenciais no navegador', 'CORS permissivo', 'ausencia de auditoria', 'rate limit insuficiente'],
        'validacao': ['autenticacao JWT', 'bloqueio de conteudo sensivel', 'correlation_id', 'logs auditaveis'],
        'correlation_id': correlation_id,
        'fingerprint': gerar_fingerprint(contexto + entrada),
    }, ensure_ascii=False)


def executar_provider(provider: Provider, prompt: str, contexto: str, entrada: str, correlation_id: str) -> str:
    if provider == 'mock':
        return resposta_mock(contexto, entrada, correlation_id)
    if provider == 'ollama':
        return chamar_ollama(prompt)
    if provider == 'openai':
        return chamar_openai(prompt)
    if provider == 'claude':
        return chamar_claude(prompt)
    raise RuntimeError(f'Provider nao suportado: {provider}')


def publicar_reqsys(payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.codex_reqsys_endpoint:
        return {'publicado': False, 'motivo': 'CODEX_REQSYS_ENDPOINT ausente'}
    headers = {'Content-Type': 'application/json'}
    if settings.codex_reqsys_key:
        headers['Authorization'] = f'Bearer {settings.codex_reqsys_key}'
    data = _post_json(settings.codex_reqsys_endpoint, payload, headers=headers, timeout=20)
    return {'publicado': True, 'resposta': data}


def auditar(evento: str, payload: dict[str, Any]) -> None:
    audit_logger.info('%s %s', evento, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def analisar_governado(
    *,
    provider: Provider,
    contexto: str,
    entrada: str,
    usuario: dict[str, Any],
    correlation_id: str | None,
    publicar_no_reqsys: bool,
) -> dict[str, Any]:
    cid = gerar_correlation_id(correlation_id)
    user_id = str(usuario.get('sub') or usuario.get('email') or 'desconhecido')
    permitido, retry_after = rate_limit_state.consumir(user_id)
    if not permitido:
        return {'bloqueado': True, 'motivo': 'rate_limit', 'retry_after_seconds': retry_after, 'correlation_id': cid}

    achados = validar_conteudo_seguro([contexto, entrada])
    if achados:
        auditar('codex_bloqueado', {'correlation_id': cid, 'usuario': user_id, 'motivo': 'conteudo_sensivel'})
        return {'bloqueado': True, 'motivo': 'conteudo_sensivel', 'correlation_id': cid}

    prompt = montar_prompt(contexto, entrada)
    resposta = executar_provider(provider, prompt, contexto, entrada, cid)
    reqsys_payload = {
        'correlation_id': cid,
        'origem': 'codex-governado',
        'provider': provider,
        'usuario': user_id,
        'fingerprint': gerar_fingerprint(contexto + entrada + resposta),
        'contexto': contexto[:1000],
        'resultado': resposta[:8000],
        'status': 'analise_governada_concluida',
    }
    publicacao = publicar_reqsys(reqsys_payload) if publicar_no_reqsys else {'publicado': False, 'motivo': 'publicacao_nao_solicitada'}
    auditar('codex_analisado', {'correlation_id': cid, 'usuario': user_id, 'provider': provider, 'publicado': publicacao.get('publicado')})
    return {
        'bloqueado': False,
        'correlation_id': cid,
        'provider': provider,
        'resultado': resposta,
        'reqsys_payload': reqsys_payload,
        'reqsys_publicacao': publicacao,
    }
