"""Consenso multipass e validação governada de nomes de pessoas.

O módulo é stdlib-puro e não executa OCR. Ele recebe leituras independentes de
um adaptador OCR e produz um consenso auditável, com confiança global,
confiança por caractere, detecção de ambiguidades e decisão fail-closed.

Princípios:
- nunca corrige um nome consultando dicionário de nomes;
- não inventa caracteres ausentes sem apoio de múltiplas leituras;
- qualquer inserção/remoção não resolvida bloqueia AUTO;
- caracteres incompatíveis com nome humano bloqueiam AUTO;
- a forma de exibição preserva acentos; a forma de comparação remove acentos.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from statistics import fmean
from typing import Iterable

__all__ = [
    "EstadoConsensoNome",
    "LeituraOCRNome",
    "VotoCaractere",
    "ResultadoConsensoNome",
    "normalizar_nome_exibicao",
    "normalizar_nome_comparacao",
    "consensuar_nome",
    "consolidar_ocorrencias_nome",
]


class EstadoConsensoNome(Enum):
    AUTO = "AUTO"
    VALIDACAO_ADICIONAL = "VALIDACAO_ADICIONAL"
    REVISAO = "REVISAO"
    ABSTENCAO = "ABSTENCAO"


@dataclass(frozen=True)
class LeituraOCRNome:
    texto: str
    confianca: float
    origem: str = ""
    confiancas_caracteres: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.confianca) <= 1.0:
            raise ValueError("confianca deve estar entre 0 e 1")
        if any(not 0.0 <= float(c) <= 1.0 for c in self.confiancas_caracteres):
            raise ValueError("confiancas_caracteres deve conter valores entre 0 e 1")


@dataclass(frozen=True)
class VotoCaractere:
    indice: int
    caractere: str
    suporte: float
    confianca_ocr: float
    alternativas: tuple[str, ...] = ()
    ambiguidade_visual: bool = False

    def to_dict(self) -> dict:
        return {
            "indice": self.indice,
            "caractere": self.caractere,
            "suporte": round(self.suporte, 6),
            "confianca_ocr": round(self.confianca_ocr, 6),
            "alternativas": list(self.alternativas),
            "ambiguidade_visual": self.ambiguidade_visual,
        }


@dataclass(frozen=True)
class ResultadoConsensoNome:
    valor: str
    valor_normalizado: str
    confianca: float
    estado: EstadoConsensoNome
    leituras_validas: int
    total_leituras: int
    votos: tuple[VotoCaractere, ...] = ()
    motivos: tuple[str, ...] = ()
    houve_insercao_remocao: bool = False
    ocorrencias_concordantes: int = 1

    @property
    def exige_revisao_humana(self) -> bool:
        return self.estado in {
            EstadoConsensoNome.VALIDACAO_ADICIONAL,
            EstadoConsensoNome.REVISAO,
        }

    def to_dict(self, incluir_pii: bool = True) -> dict:
        dados = {
            "confianca": round(self.confianca, 6),
            "estado": self.estado.value,
            "leituras_validas": self.leituras_validas,
            "total_leituras": self.total_leituras,
            "motivos": list(self.motivos),
            "houve_insercao_remocao": self.houve_insercao_remocao,
            "ocorrencias_concordantes": self.ocorrencias_concordantes,
        }
        if incluir_pii:
            dados["valor"] = self.valor
            dados["valor_normalizado"] = self.valor_normalizado
            dados["votos"] = [v.to_dict() for v in self.votos]
        return dados


_ESPACOS = re.compile(r"\s+")
_GRUPOS_CONFUSAO = ("0OQD", "1IL7", "5S", "8B", "2Z", "6G", "9G", "UV", "CG", "MN")
_MAPA_CONFUSAO: dict[str, set[str]] = {}
for grupo in _GRUPOS_CONFUSAO:
    for char in grupo:
        _MAPA_CONFUSAO.setdefault(char, set()).update(set(grupo) - {char})


def normalizar_nome_exibicao(valor: str) -> str:
    valor = unicodedata.normalize("NFC", (valor or "").strip())
    valor = _ESPACOS.sub(" ", valor)
    return valor.upper()


def normalizar_nome_comparacao(valor: str) -> str:
    valor = unicodedata.normalize("NFKD", normalizar_nome_exibicao(valor))
    return "".join(c for c in valor if not unicodedata.combining(c))


def _distancia_levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        atual = [i]
        for j, cb in enumerate(b, start=1):
            atual.append(min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = atual
    return anterior[-1]


def _alinhar(referencia: str, outra: str) -> tuple[list[tuple[str | None, str | None]], bool]:
    n, m = len(referencia), len(outra)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            custo_sub = 0 if referencia[i - 1] == outra[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j - 1] + custo_sub, dp[i - 1][j] + 1, dp[i][j - 1] + 1)
    i, j = n, m
    alinhado: list[tuple[str | None, str | None]] = []
    houve_indel = False
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            custo_sub = 0 if referencia[i - 1] == outra[j - 1] else 1
            if dp[i][j] == dp[i - 1][j - 1] + custo_sub:
                alinhado.append((referencia[i - 1], outra[j - 1]))
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            alinhado.append((referencia[i - 1], None))
            houve_indel = True
            i -= 1
        else:
            alinhado.append((None, outra[j - 1]))
            houve_indel = True
            j -= 1
    alinhado.reverse()
    return alinhado, houve_indel


def _escolher_ancora(leituras: list[LeituraOCRNome]) -> int:
    textos = [normalizar_nome_exibicao(x.texto) for x in leituras]
    melhor = 0
    melhor_chave: tuple[float, float, int] | None = None
    for i, leitura in enumerate(leituras):
        custo = 0.0
        for j, outra in enumerate(leituras):
            if i != j:
                custo += _distancia_levenshtein(textos[i], textos[j]) * (0.5 + outra.confianca)
        chave = (custo, -leitura.confianca, i)
        if melhor_chave is None or chave < melhor_chave:
            melhor_chave = chave
            melhor = i
    return melhor


def _caractere_permitido_nome(char: str) -> bool:
    return char.isalpha() or char in {" ", "-", "'", "’", "."}


def _eh_ambiguidade_visual(chars: Iterable[str]) -> bool:
    unicos = {c for c in chars if c}
    if len(unicos) <= 1:
        return False
    return any(all(b == a or b in _MAPA_CONFUSAO.get(a, set()) for b in unicos) for a in unicos)


def consensuar_nome(
    leituras: Iterable[LeituraOCRNome],
    *,
    limiar_auto: float = 0.98,
    limiar_validacao: float = 0.90,
    suporte_minimo_caractere: float = 0.67,
    minimo_leituras: int = 3,
) -> ResultadoConsensoNome:
    todas = list(leituras)
    validas = [x for x in todas if normalizar_nome_exibicao(x.texto)]
    if not validas:
        return ResultadoConsensoNome("", "", 0.0, EstadoConsensoNome.ABSTENCAO, 0, len(todas), motivos=("nenhuma leitura OCR não vazia",))

    ancora = normalizar_nome_exibicao(validas[_escolher_ancora(validas)].texto)
    pesos = [max(0.05, x.confianca) for x in validas]
    mapas: list[dict[int, tuple[str, float]]] = []
    pesos_indel = 0.0
    for leitura, peso in zip(validas, pesos):
        alinhamento, indel = _alinhar(ancora, normalizar_nome_exibicao(leitura.texto))
        if indel:
            pesos_indel += peso
        mapa: dict[int, tuple[str, float]] = {}
        pos_ref = pos_outro = -1
        conf_chars = leitura.confiancas_caracteres
        texto_norm = normalizar_nome_exibicao(leitura.texto)
        usar_conf_chars = len(conf_chars) == len(texto_norm)
        for ref, outro in alinhamento:
            if outro is not None:
                pos_outro += 1
            if ref is not None:
                pos_ref += 1
                if outro is not None:
                    mapa[pos_ref] = (outro, conf_chars[pos_outro] if usar_conf_chars else leitura.confianca)
        mapas.append(mapa)

    votos_saida: list[VotoCaractere] = []
    chars_saida: list[str] = []
    motivos: list[str] = []
    suporte_baixo = False
    for pos, char_ancora in enumerate(ancora):
        por_char: dict[str, float] = {}
        conf_por_char: dict[str, list[tuple[float, float]]] = {}
        for mapa, peso in zip(mapas, pesos):
            item = mapa.get(pos)
            if item is not None:
                char, conf_char = item
                peso_char = peso * max(0.05, conf_char)
                por_char[char] = por_char.get(char, 0.0) + peso_char
                conf_por_char.setdefault(char, []).append((conf_char, peso))
        if not por_char:
            chars_saida.append(char_ancora)
            votos_saida.append(VotoCaractere(pos, char_ancora, 0.0, 0.0))
            suporte_baixo = True
            continue
        ordenados = sorted(por_char.items(), key=lambda item: (-item[1], item[0]))
        escolhido, peso_escolhido = ordenados[0]
        total = sum(por_char.values())
        suporte = peso_escolhido / total if total else 0.0
        pares_conf = conf_por_char.get(escolhido, [])
        soma_pesos_conf = sum(p for _, p in pares_conf)
        conf_ocr_char = sum(c * p for c, p in pares_conf) / soma_pesos_conf if soma_pesos_conf else 0.0
        if suporte < suporte_minimo_caractere:
            suporte_baixo = True
        chars_saida.append(escolhido)
        votos_saida.append(VotoCaractere(pos, escolhido, suporte, conf_ocr_char, tuple(c for c, _ in ordenados[1:]), _eh_ambiguidade_visual(por_char)))

    valor = normalizar_nome_exibicao("".join(chars_saida))
    valor_normalizado = normalizar_nome_comparacao(valor)
    suportes = [v.suporte for v in votos_saida if v.caractere.strip()]
    confs_chars = [v.confianca_ocr for v in votos_saida if v.caractere.strip()]
    suporte_medio = fmean(suportes) if suportes else 0.0
    conf_char_media = fmean(confs_chars) if confs_chars else 0.0
    inliers = [x for x in validas if normalizar_nome_exibicao(x.texto) == valor]
    conf_ocr = fmean(x.confianca for x in inliers) if len(inliers) >= 2 else sum(x.confianca * p for x, p in zip(validas, pesos)) / sum(pesos)
    confianca = max(0.0, min(0.999999, 0.55 * suporte_medio + 0.25 * conf_char_media + 0.20 * conf_ocr))

    peso_total = sum(pesos)
    houve_indel = pesos_indel / peso_total >= 0.25 if peso_total else False
    chars_invalidos = sorted({c for c in valor if not _caractere_permitido_nome(c)})
    if len(validas) < minimo_leituras:
        motivos.append(f"leituras válidas insuficientes: {len(validas)} < {minimo_leituras}")
    if houve_indel:
        motivos.append("houve inserção/remoção entre leituras")
    if suporte_baixo:
        motivos.append("há caractere com suporte abaixo do mínimo")
    if chars_invalidos:
        motivos.append("nome contém caractere incompatível com campo textual")
    if not any(c.isalpha() for c in valor):
        motivos.append("resultado não contém letras")
    if any(c.isdigit() for c in valor):
        motivos.append("nome contém dígito e exige revisão")

    if confianca >= limiar_auto and not motivos:
        estado = EstadoConsensoNome.AUTO
    elif confianca >= limiar_validacao:
        estado = EstadoConsensoNome.VALIDACAO_ADICIONAL
        if confianca < limiar_auto:
            motivos.append(f"confiança {confianca:.4f} abaixo do limiar AUTO {limiar_auto:.4f}")
    else:
        estado = EstadoConsensoNome.REVISAO
        motivos.append(f"confiança {confianca:.4f} abaixo do limiar de validação {limiar_validacao:.4f}")

    return ResultadoConsensoNome(valor, valor_normalizado, confianca, estado, len(validas), len(todas), tuple(votos_saida), tuple(dict.fromkeys(motivos)), houve_indel)


def consolidar_ocorrencias_nome(resultados: Iterable[ResultadoConsensoNome], *, limiar_auto: float = 0.98) -> ResultadoConsensoNome:
    itens = [r for r in resultados if r.valor_normalizado]
    if not itens:
        return ResultadoConsensoNome("", "", 0.0, EstadoConsensoNome.ABSTENCAO, 0, 0, motivos=("nenhuma ocorrência válida do nome",), ocorrencias_concordantes=0)
    grupos: dict[str, list[ResultadoConsensoNome]] = {}
    for item in itens:
        grupos.setdefault(item.valor_normalizado, []).append(item)
    chave, vencedores = sorted(grupos.items(), key=lambda x: (-len(x[1]), -fmean(r.confianca for r in x[1]), x[0]))[0]
    base = max(vencedores, key=lambda r: r.confianca)
    concordantes = len(vencedores)
    divergentes = len(itens) - concordantes
    confianca = min(0.999999, fmean(r.confianca for r in vencedores) + min(0.02, 0.01 * (concordantes - 1)))
    motivos = list(base.motivos)
    if divergentes:
        motivos.append(f"{divergentes} ocorrência(s) divergem do consenso")
    if concordantes < 2:
        motivos.append("sem repetição concordante para validação contextual")
    if divergentes == 0 and concordantes >= 2 and confianca >= limiar_auto and base.estado is EstadoConsensoNome.AUTO:
        estado = EstadoConsensoNome.AUTO
    elif confianca >= 0.90:
        estado = EstadoConsensoNome.VALIDACAO_ADICIONAL
    else:
        estado = EstadoConsensoNome.REVISAO
    return ResultadoConsensoNome(base.valor, chave, confianca, estado, sum(r.leituras_validas for r in itens), sum(r.total_leituras for r in itens), base.votos, tuple(dict.fromkeys(motivos)), any(r.houve_insercao_remocao for r in itens), concordantes)
