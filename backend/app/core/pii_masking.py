"""Mascaramento de PII para logs e superficies nao controladas (ADR-002).

Este modulo centraliza o mascaramento aplicado anteriormente so no pipeline de
RAG (`app.services.rag_governado`) para que qualquer ponto do backend que loga
dados de usuario (ex.: `app/api/auth.py`) use a mesma logica, em vez de cada
servico reimplementar sua propria regex.
"""

from __future__ import annotations

import re

PII_PATTERNS = (
    re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),
    re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'),
)


def mascarar_pii(texto: str) -> str:
    """Redige qualquer CPF/e-mail encontrado em texto livre (uso em respostas de IA/RAG)."""
    texto_mascarado = texto
    for pattern in PII_PATTERNS:
        texto_mascarado = pattern.sub('[DADO_MASCARADO]', texto_mascarado)
    return texto_mascarado


def mascarar_email(email: str | None) -> str:
    """Mascara parcial preservando o dominio, para logs operacionais: u***@dominio.com."""
    if not email or '@' not in email:
        return '[DADO_MASCARADO]'
    usuario, dominio = email.split('@', 1)
    inicial = usuario[0] if usuario else 'u'
    return f'{inicial}***@{dominio}'


def mascarar_cpf(cpf: str | None) -> str:
    """Mascara parcial de CPF para logs operacionais: ***.456.789-**."""
    digitos = re.sub(r'\D', '', cpf or '')
    if len(digitos) != 11:
        return '[DADO_MASCARADO]'
    return f'***.{digitos[3:6]}.{digitos[6:9]}-**'


def mascarar_token(_token: str | None) -> str:
    """Tokens/segredos nunca sao parcialmente exibidos em log — sempre redigidos por completo."""
    return '[SEGREDO_REMOVIDO]'
