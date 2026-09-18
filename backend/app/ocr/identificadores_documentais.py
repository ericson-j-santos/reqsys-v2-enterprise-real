"""Validação semântica de identificadores documentais brasileiros em texto OCR.

Este módulo fecha a lacuna declarada em `docs/architecture/ocr-evidence-gate-v2.md`
("não cria novos parsers de domínio para validar juridicamente CPF, RG/CIN ou CNH").
Ele classifica identificadores lidos pelo OCR como estruturalmente válidos,
inválidos ou não verificáveis, reduzindo falso positivo de leitura.

Princípios inegociáveis:

- **Fail-closed.** Sem rótulo âncora não há detecção; sem dígito verificador
  verificável o estado é `VALIDACAO_INDISPONIVEL`, nunca `VALIDO`.
- **Nunca dispensa revisão humana.** `requer_validacao_humana` é sempre `True`.
  Validade estrutural de dígito verificador não é prova de autenticidade
  documental nem de titularidade.
- **Sem PII em claro.** O valor detectado nunca é retornado nem serializado.
  A evidência publicável carrega apenas tipo, estado e fingerprint com chave.
- **Não fabrica dado.** A normalização de confusões de OCR é registrada como
  estado próprio (`VALIDO_APOS_CORRECAO_OCR`), jamais promovida a `VALIDO`.

O módulo é stdlib-puro e não executa OCR: recebe texto já extraído.
"""
from __future__ import annotations

import hmac
import os
import re
import secrets
import unicodedata
from dataclasses import dataclass, replace
from hashlib import sha256

SCHEMA_VERSION = '1.0.0'

TIPO_CPF = 'CPF'
TIPO_CNH = 'CNH'
TIPO_CIN = 'CIN'
TIPO_RG = 'RG'

TIPOS_SUPORTADOS = (TIPO_CPF, TIPO_CNH, TIPO_CIN, TIPO_RG)

ESTADO_VALIDO = 'VALIDO'
ESTADO_VALIDO_APOS_CORRECAO_OCR = 'VALIDO_APOS_CORRECAO_OCR'
ESTADO_INVALIDO = 'INVALIDO'
ESTADO_VALIDACAO_INDISPONIVEL = 'VALIDACAO_INDISPONIVEL'
ESTADO_FORMATO_INESPERADO = 'FORMATO_INESPERADO'

ESTADOS = (
    ESTADO_VALIDO,
    ESTADO_VALIDO_APOS_CORRECAO_OCR,
    ESTADO_INVALIDO,
    ESTADO_VALIDACAO_INDISPONIVEL,
    ESTADO_FORMATO_INESPERADO,
)

#: Estados que jamais podem ser tratados como leitura confiável por automação.
ESTADOS_NAO_CONFIAVEIS = (
    ESTADO_INVALIDO,
    ESTADO_VALIDACAO_INDISPONIVEL,
    ESTADO_FORMATO_INESPERADO,
)

ENV_CHAVE_FINGERPRINT = 'OCR_IDENTIFIER_FINGERPRINT_KEY'

ESCOPO_FINGERPRINT_PERSISTENTE = 'PERSISTENTE'
ESCOPO_FINGERPRINT_EFEMERO = 'EFEMERO'

#: Janela de caracteres inspecionada após o rótulo. Mantida curta para evitar
#: capturar o identificador de um campo vizinho em documento multi-coluna.
JANELA_APOS_ROTULO = 48

_MAX_CARACTERES_TEXTO = 200_000
_MAX_IDENTIFICADORES = 500

# Confusões de OCR restritas a campos numéricos. Não corrigimos o inverso
# (dígito -> letra) porque o campo esperado é numérico por definição.
_CORRECOES_OCR = {
    'O': '0', 'Q': '0', 'D': '0',
    'I': '1', 'L': '1', '|': '1',
    'Z': '2',
    'S': '5',
    'G': '6',
    'T': '7',
    'B': '8',
    'A': '4',
}

_ROTULOS = (
    # (tipo, padrão do rótulo). Ordem importa: rótulos mais específicos antes.
    (TIPO_CPF, r'C\.?\s?P\.?\s?F\.?'),
    (TIPO_CNH, r'C\.?\s?N\.?\s?H\.?'),
    (TIPO_CNH, r'(?:N[UO]MERO\s+DE\s+)?REGISTRO(?:\s+DE\s+HABILITACAO)?'),
    (TIPO_CNH, r'HABILITACAO'),
    (TIPO_CIN, r'C\.?\s?I\.?\s?N\.?'),
    (TIPO_CIN, r'(?:CARTEIRA\s+DE\s+)?IDENTIDADE\s+NACIONAL'),
    (TIPO_RG, r'R\.?\s?G\.?'),
    (TIPO_RG, r'REGISTRO\s+GERAL'),
    (TIPO_RG, r'(?:CARTEIRA\s+DE\s+)?IDENTIDADE'),
)

_DIGITOS_ESPERADOS = {
    TIPO_CPF: (11,),
    TIPO_CNH: (11,),
    TIPO_CIN: (11,),
    # RG é estadual e não possui formato nacional; aceitamos a faixa usual
    # apenas para reconhecer o campo, nunca para validá-lo.
    TIPO_RG: (7, 8, 9, 10, 11),
}

_chave_efemera: bytes | None = None


class ChaveFingerprintAusente(RuntimeError):
    """Fingerprint persistente foi exigido sem chave configurada."""


@dataclass(frozen=True)
class IdentificadorDocumental:
    """Ocorrência de identificador documental avaliada a partir de texto OCR.

    O valor lido nunca é armazenado neste objeto. `mascara` revela apenas os
    dois últimos dígitos (verificadores, quando existem) para permitir
    conferência humana contra o documento físico.
    """

    tipo: str
    estado: str
    rotulo: str
    mascara: str
    fingerprint: str
    fingerprint_escopo: str
    digitos: int
    correcoes_ocr: int
    pagina: int | None = None
    confianca_ocr: float = 1.0
    requer_validacao_humana: bool = True

    def __post_init__(self) -> None:
        if self.requer_validacao_humana is not True:
            raise ValueError('identificador documental sempre exige revisão humana')
        if self.tipo not in TIPOS_SUPORTADOS:
            raise ValueError(f'tipo não suportado: {self.tipo}')
        if self.estado not in ESTADOS:
            raise ValueError(f'estado não suportado: {self.estado}')

    @property
    def confiavel(self) -> bool:
        """Leitura estruturalmente consistente. Não implica autenticidade."""
        return self.estado in (ESTADO_VALIDO, ESTADO_VALIDO_APOS_CORRECAO_OCR)

    def para_evidencia(self) -> dict[str, object]:
        """Projeção publicável em CI: sem máscara e sem qualquer dígito lido."""
        return {
            'tipo': self.tipo,
            'estado': self.estado,
            'rotulo': self.rotulo,
            'digitos': self.digitos,
            'correcoes_ocr': self.correcoes_ocr,
            'pagina': self.pagina,
            'confianca_ocr': round(self.confianca_ocr, 6),
            'fingerprint': self.fingerprint,
            'fingerprint_escopo': self.fingerprint_escopo,
            'requer_validacao_humana': True,
        }


def _normalizar_texto(texto: str) -> str:
    sem_acento = ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    )
    return sem_acento.upper()


def _somente_digitos(bruto: str) -> str:
    return ''.join(c for c in bruto if c.isdigit())


def _corrigir_ocr(bruto: str) -> tuple[str, int]:
    """Aplica confusões OCR letra->dígito. Retorna (dígitos, nº de correções)."""
    digitos: list[str] = []
    correcoes = 0
    for caractere in bruto:
        if caractere.isdigit():
            digitos.append(caractere)
        elif caractere in _CORRECOES_OCR:
            digitos.append(_CORRECOES_OCR[caractere])
            correcoes += 1
    return ''.join(digitos), correcoes


def _repetido(digitos: str) -> bool:
    return len(set(digitos)) == 1


def _dv_cpf(base: str) -> str:
    """Dígitos verificadores de CPF pelo módulo 11 (Receita Federal)."""
    def _digito(parcial: str, peso_inicial: int) -> str:
        soma = sum(int(d) * (peso_inicial - i) for i, d in enumerate(parcial))
        resto = (soma * 10) % 11
        return '0' if resto == 10 else str(resto)

    primeiro = _digito(base[:9], 10)
    segundo = _digito(base[:9] + primeiro, 11)
    return primeiro + segundo


def validar_cpf(digitos: str) -> bool:
    """Valida CPF por dígito verificador, rejeitando sequências repetidas."""
    if len(digitos) != 11 or not digitos.isdigit() or _repetido(digitos):
        return False
    return _dv_cpf(digitos) == digitos[9:]


def _dv_cnh(base: str) -> str | None:
    """Dígitos verificadores de CNH pelo módulo 11 (padrão Denatran).

    Retorna `None` no ramo em que o segundo verificador ficaria negativo após
    o desconto. As implementações públicas divergem nesse ramo e afirmar um
    resultado seria fabricar evidência, então ele é tratado como indeterminado.
    """
    soma = sum(int(d) * (9 - i) for i, d in enumerate(base[:9]))
    primeiro = soma % 11
    desconto = 0
    if primeiro >= 10:
        primeiro = 0
        desconto = 2

    soma = sum(int(d) * (1 + i) for i, d in enumerate(base[:9]))
    resto = soma % 11
    if resto >= 10:
        segundo = 0
    elif resto - desconto >= 0:
        segundo = resto - desconto
    else:
        return None
    return f'{primeiro}{segundo}'


def validar_cnh(digitos: str) -> bool | None:
    """Valida CNH por dígito verificador.

    Returns:
        `True`/`False` quando o verificador é determinável e `None` quando o
        algoritmo não determina o segundo dígito sem ambiguidade.
    """
    if len(digitos) != 11 or not digitos.isdigit() or _repetido(digitos):
        return False
    esperado = _dv_cnh(digitos)
    if esperado is None:
        return None
    return esperado == digitos[9:]


def _chave_fingerprint(chave: bytes | None) -> tuple[bytes, str]:
    global _chave_efemera
    if chave:
        return chave, ESCOPO_FINGERPRINT_PERSISTENTE

    configurada = os.getenv(ENV_CHAVE_FINGERPRINT, '').strip()
    if configurada:
        return configurada.encode('utf-8'), ESCOPO_FINGERPRINT_PERSISTENTE

    # Sem chave configurada o fingerprint vale apenas para correlacionar
    # ocorrências dentro do mesmo processo. Um SHA-256 sem chave sobre 11
    # dígitos é reversível por força bruta em espaço de 10^11, então nunca
    # emitimos fingerprint sem chave.
    if _chave_efemera is None:
        _chave_efemera = secrets.token_bytes(32)
    return _chave_efemera, ESCOPO_FINGERPRINT_EFEMERO


def _fingerprint(tipo: str, digitos: str, chave: bytes) -> str:
    return hmac.new(chave, f'{tipo}:{digitos}'.encode('utf-8'), sha256).hexdigest()


def _mascarar(tipo: str, digitos: str) -> str:
    if len(digitos) <= 2:
        return '*' * len(digitos)
    visivel = digitos[-2:]
    oculto = '*' * (len(digitos) - 2)
    if tipo in (TIPO_CPF, TIPO_CIN) and len(digitos) == 11:
        return f'***.***.***-{visivel}'
    return f'{oculto}{visivel}'


def _classificar(tipo: str, digitos_lidos: str, correcoes: int) -> tuple[str, str]:
    """Retorna (tipo efetivo, estado) para os dígitos já normalizados."""
    esperado = _DIGITOS_ESPERADOS[tipo]
    if len(digitos_lidos) not in esperado:
        return tipo, ESTADO_FORMATO_INESPERADO

    # A CIN adota o número do CPF como identificador único (Decreto 10.977/2022),
    # portanto é verificável pelo mesmo dígito verificador.
    if tipo in (TIPO_CPF, TIPO_CIN):
        if validar_cpf(digitos_lidos):
            return tipo, ESTADO_VALIDO if correcoes == 0 else ESTADO_VALIDO_APOS_CORRECAO_OCR
        return tipo, ESTADO_INVALIDO

    if tipo == TIPO_CNH:
        veredito = validar_cnh(digitos_lidos)
        if veredito is None:
            return tipo, ESTADO_VALIDACAO_INDISPONIVEL
        if veredito:
            return tipo, ESTADO_VALIDO if correcoes == 0 else ESTADO_VALIDO_APOS_CORRECAO_OCR
        return tipo, ESTADO_INVALIDO

    # RG é emitido por órgão estadual, sem dígito verificador nacional
    # padronizado. Declarar "válido" aqui seria fabricar evidência.
    return TIPO_RG, ESTADO_VALIDACAO_INDISPONIVEL


def _padrao_rotulos() -> re.Pattern[str]:
    alternativas = '|'.join(f'(?P<t{i}>{padrao})' for i, (_, padrao) in enumerate(_ROTULOS))
    # Após o rótulo aceitamos uma sigla entre parênteses ("Identidade
    # Nacional (CIN):"), a abreviação de número e a pontuação separadora.
    sufixo = r'\s*(?:\([A-Z.\s]{1,12}\))?\s*(?:N[UO]?\.?|NUMERO)?\s*[:\-]?\s*'
    return re.compile(rf'\b(?:{alternativas}){sufixo}')


_RE_ROTULOS = _padrao_rotulos()
_RE_CAMPO = re.compile(r'[0-9OQDILZSGTBA|][0-9OQDILZSGTBA|.\-/ ]{4,24}')


def detectar_identificadores(
    texto: str,
    *,
    pagina: int | None = None,
    confianca_ocr: float = 1.0,
    chave_fingerprint: bytes | None = None,
) -> list[IdentificadorDocumental]:
    """Detecta e classifica identificadores documentais ancorados por rótulo.

    Args:
        texto: texto extraído por OCR (ou nativo) de uma página.
        pagina: número da página de origem, preservado na evidência.
        confianca_ocr: confiança média do OCR para a página, em [0, 1].
        chave_fingerprint: chave HMAC. Ausente, usa `OCR_IDENTIFIER_FINGERPRINT_KEY`
            e, em último caso, uma chave efêmera de processo.

    Returns:
        Lista de ocorrências, sem duplicatas por (tipo, fingerprint, página).
    """
    if not texto or not texto.strip():
        return []

    chave, escopo = _chave_fingerprint(chave_fingerprint)
    normalizado = _normalizar_texto(texto[:_MAX_CARACTERES_TEXTO])
    confianca = min(1.0, max(0.0, float(confianca_ocr)))

    encontrados: list[IdentificadorDocumental] = []
    vistos: set[tuple[str, str]] = set()

    for match in _RE_ROTULOS.finditer(normalizado):
        indice = next(
            i for i, (_, _) in enumerate(_ROTULOS)
            if match.group(f't{i}') is not None
        )
        tipo_rotulo, _ = _ROTULOS[indice]
        rotulo = re.sub(r'\s+', ' ', match.group(0)).strip(' :-')

        janela = normalizado[match.end():match.end() + JANELA_APOS_ROTULO]
        # O campo precisa começar no início da janela: um número distante do
        # rótulo pertence a outro campo e capturá-lo geraria falso positivo.
        campo = _RE_CAMPO.match(janela)
        if not campo:
            continue

        bruto = campo.group(0)
        digitos_literais = _somente_digitos(bruto)
        digitos_corrigidos, correcoes = _corrigir_ocr(bruto)

        # Preferimos a leitura literal. A leitura corrigida só substitui a
        # literal quando confirma o verificador, ou quando a literal sequer
        # tem o comprimento do campo e a corrigida tem — nesse caso o estado
        # da corrigida vale como está, inclusive INVALIDO.
        tipo, estado = _classificar(tipo_rotulo, digitos_literais, 0)
        digitos = digitos_literais
        correcoes_aplicadas = 0
        if correcoes and estado in (ESTADO_INVALIDO, ESTADO_FORMATO_INESPERADO):
            tipo_alt, estado_alt = _classificar(tipo_rotulo, digitos_corrigidos, correcoes)
            confirma = estado_alt in (ESTADO_VALIDO, ESTADO_VALIDO_APOS_CORRECAO_OCR)
            recupera_formato = (
                estado == ESTADO_FORMATO_INESPERADO
                and estado_alt != ESTADO_FORMATO_INESPERADO
            )
            if confirma or recupera_formato:
                tipo = tipo_alt
                estado = ESTADO_VALIDO_APOS_CORRECAO_OCR if confirma else estado_alt
                digitos = digitos_corrigidos
                correcoes_aplicadas = correcoes

        if not digitos:
            continue

        fingerprint = _fingerprint(tipo, digitos, chave)
        chave_dedupe = (tipo, fingerprint)
        if chave_dedupe in vistos:
            continue
        vistos.add(chave_dedupe)

        encontrados.append(
            IdentificadorDocumental(
                tipo=tipo,
                estado=estado,
                rotulo=rotulo,
                mascara=_mascarar(tipo, digitos),
                fingerprint=fingerprint,
                fingerprint_escopo=escopo,
                digitos=len(digitos),
                correcoes_ocr=correcoes_aplicadas,
                pagina=pagina,
                confianca_ocr=confianca,
            )
        )
        if len(encontrados) >= _MAX_IDENTIFICADORES:
            break

    return encontrados


def detectar_identificadores_por_paginas(
    paginas: list[tuple[int, str, float]],
    *,
    chave_fingerprint: bytes | None = None,
) -> list[IdentificadorDocumental]:
    """Aplica a detecção página a página, preservando a página de origem."""
    resultado: list[IdentificadorDocumental] = []
    for pagina, texto, confianca in paginas:
        for item in detectar_identificadores(
            texto,
            pagina=pagina,
            confianca_ocr=confianca,
            chave_fingerprint=chave_fingerprint,
        ):
            resultado.append(replace(item, pagina=pagina))
    return resultado


def resumo_evidencia(
    identificadores: list[IdentificadorDocumental],
) -> dict[str, object]:
    """Agregado sanitizado para publicação em trilha de evidência."""
    por_tipo: dict[str, int] = {}
    por_estado: dict[str, int] = {}
    for item in identificadores:
        por_tipo[item.tipo] = por_tipo.get(item.tipo, 0) + 1
        por_estado[item.estado] = por_estado.get(item.estado, 0) + 1

    return {
        'schema_version': SCHEMA_VERSION,
        'total': len(identificadores),
        'por_tipo': dict(sorted(por_tipo.items())),
        'por_estado': dict(sorted(por_estado.items())),
        'confiaveis': sum(1 for item in identificadores if item.confiavel),
        'todos_exigem_revisao_humana': all(
            item.requer_validacao_humana for item in identificadores
        ),
        'contem_dado_pessoal': False,
    }
