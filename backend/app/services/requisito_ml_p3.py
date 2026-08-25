from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from app.services.requisito_classifier import CATEGORIAS, avaliar_classificador, classificar_requisito
from app.services.requisito_ml import (
    MODELO_VERSAO,
    ClassificadorRequisitoSupervisionado,
    RegistroTreinoML,
    carregar_dataset_ml,
)

MODOS_RUNTIME = ('off', 'shadow', 'canary', 'active')
STATUS_REVISAO = ('PENDENTE_HUMANA', 'APROVADO', 'REJEITADO')
HOLDOUT_VERSAO = 'requisitos-holdout-p3-v1'

_PADROES_PII = (
    re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b'),
    re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b'),
    re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b'),
    re.compile(r'\b(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}\b'),
)


@dataclass(frozen=True)
class RegistroHoldoutML:
    id: str
    texto: str
    categoria: str
    origem: str
    dataset_versao: str


@dataclass(frozen=True)
class RegistroObservadoML:
    id: str
    texto: str
    source_ref: str
    categoria_sugerida: str
    anonimizado: bool
    revisao_status: str
    categoria_revisada: str | None = None
    revisor_ref: str | None = None


@dataclass(frozen=True)
class PoliticaRuntimeML:
    versao: str
    modelo_versao: str
    holdout_versao: str
    holdout_sha256: str
    modo_padrao: str
    canary_percentual: float
    confianca_minima_modelo: float
    macro_f1_holdout_minimo: float
    ganho_f1_holdout_minimo: float
    js_divergence_alerta: float
    taxa_baixa_confianca_alerta: float
    distribuicao_referencia: dict[str, float]


@dataclass(frozen=True)
class DecisaoRuntimeML:
    categoria: str
    confianca: float
    engine: str
    modo: str
    correlation_id: str
    modelo_categoria: str | None
    modelo_confianca: float | None
    baseline_categoria: str
    canary_selected: bool
    fallback_reason: str | None
    evidencias: list[str]


@dataclass(frozen=True)
class EventoClassificacaoML:
    categoria: str
    confianca: float
    engine: str


@dataclass(frozen=True)
class ResultadoDriftML:
    total: int
    js_divergence: float
    taxa_baixa_confianca: float
    distribuicao_observada: dict[str, float]
    delta_por_categoria: dict[str, float]
    alertas: list[str]

    def como_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResultadoHoldoutML:
    holdout_sha256: str
    quantidade: int
    baseline_macro_f1: float
    modelo_macro_f1: float
    ganho_macro_f1: float
    status: str
    criterios: dict[str, bool]

    def como_dict(self) -> dict:
        return asdict(self)


def _normalizar_distribuicao(distribuicao: dict[str, float]) -> dict[str, float]:
    desconhecidas = set(distribuicao) - set(CATEGORIAS)
    if desconhecidas:
        raise ValueError(f'categorias desconhecidas na distribuição: {sorted(desconhecidas)}')
    valores = {categoria: float(distribuicao.get(categoria, 0.0)) for categoria in CATEGORIAS}
    if any(valor < 0 for valor in valores.values()):
        raise ValueError('distribuição não pode conter valores negativos')
    total = sum(valores.values())
    if total <= 0:
        raise ValueError('distribuição precisa possuir massa positiva')
    return {categoria: valor / total for categoria, valor in valores.items()}


def carregar_politica_runtime(caminho: Path) -> PoliticaRuntimeML:
    item = json.loads(caminho.read_text(encoding='utf-8'))
    politica = PoliticaRuntimeML(
        versao=str(item['versao']),
        modelo_versao=str(item['modelo_versao']),
        holdout_versao=str(item['holdout_versao']),
        holdout_sha256=str(item['holdout_sha256']),
        modo_padrao=str(item['modo_padrao']).lower(),
        canary_percentual=float(item['canary_percentual']),
        confianca_minima_modelo=float(item['confianca_minima_modelo']),
        macro_f1_holdout_minimo=float(item['macro_f1_holdout_minimo']),
        ganho_f1_holdout_minimo=float(item['ganho_f1_holdout_minimo']),
        js_divergence_alerta=float(item['js_divergence_alerta']),
        taxa_baixa_confianca_alerta=float(item['taxa_baixa_confianca_alerta']),
        distribuicao_referencia=_normalizar_distribuicao(item['distribuicao_referencia']),
    )
    if politica.modelo_versao != MODELO_VERSAO:
        raise ValueError(f'política exige modelo {politica.modelo_versao}, runtime fornece {MODELO_VERSAO}')
    if politica.holdout_versao != HOLDOUT_VERSAO:
        raise ValueError(f'holdout_versao inválida: {politica.holdout_versao}')
    if not re.fullmatch(r'[0-9a-f]{64}', politica.holdout_sha256):
        raise ValueError('holdout_sha256 inválido')
    if politica.modo_padrao not in MODOS_RUNTIME:
        raise ValueError(f'modo_padrao inválido: {politica.modo_padrao}')
    if not 0 <= politica.canary_percentual <= 100:
        raise ValueError('canary_percentual deve estar entre 0 e 100')
    if not 0 <= politica.confianca_minima_modelo <= 1:
        raise ValueError('confianca_minima_modelo deve estar entre 0 e 1')
    if not 0 <= politica.macro_f1_holdout_minimo <= 1:
        raise ValueError('macro_f1_holdout_minimo deve estar entre 0 e 1')
    if politica.ganho_f1_holdout_minimo < 0:
        raise ValueError('ganho_f1_holdout_minimo não pode ser negativo')
    if not 0 <= politica.js_divergence_alerta <= 1:
        raise ValueError('js_divergence_alerta deve estar entre 0 e 1')
    if not 0 <= politica.taxa_baixa_confianca_alerta <= 1:
        raise ValueError('taxa_baixa_confianca_alerta deve estar entre 0 e 1')
    return politica


def carregar_holdout(caminho: Path) -> tuple[list[RegistroHoldoutML], str]:
    conteudo = caminho.read_bytes()
    sha256 = hashlib.sha256(conteudo).hexdigest()
    registros: list[RegistroHoldoutML] = []
    ids: set[str] = set()
    for numero_linha, linha in enumerate(conteudo.splitlines(), start=1):
        if not linha.strip():
            continue
        try:
            item = json.loads(linha.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'holdout inválido na linha {numero_linha}: {exc}') from exc
        obrigatorios = {'id', 'texto', 'categoria', 'origem', 'dataset_versao'}
        ausentes = obrigatorios - set(item)
        if ausentes:
            raise ValueError(f'holdout inválido na linha {numero_linha}; ausentes: {sorted(ausentes)}')
        registro = RegistroHoldoutML(
            id=str(item['id']).strip(),
            texto=str(item['texto']).strip(),
            categoria=str(item['categoria']).strip(),
            origem=str(item['origem']).strip(),
            dataset_versao=str(item['dataset_versao']).strip(),
        )
        if not registro.id or not registro.texto or not registro.origem:
            raise ValueError(f'holdout inválido na linha {numero_linha}; valores vazios')
        if registro.id in ids:
            raise ValueError(f'id duplicado no holdout: {registro.id}')
        if registro.categoria not in CATEGORIAS:
            raise ValueError(f'categoria desconhecida no holdout: {registro.categoria}')
        if registro.dataset_versao != HOLDOUT_VERSAO:
            raise ValueError(f'versão de holdout inválida: {registro.dataset_versao}')
        ids.add(registro.id)
        registros.append(registro)
    if not registros:
        raise ValueError('holdout não pode ser vazio')
    suporte = Counter(item.categoria for item in registros)
    ausentes = [categoria for categoria in CATEGORIAS if suporte[categoria] == 0]
    if ausentes:
        raise ValueError(f'holdout sem cobertura das categorias: {ausentes}')
    return registros, sha256


def validar_holdout_imutavel(caminho: Path, politica: PoliticaRuntimeML) -> str:
    registros, sha256 = carregar_holdout(caminho)
    if not registros:
        raise ValueError('holdout não pode ser vazio')
    if sha256 != politica.holdout_sha256:
        raise ValueError(
            f'holdout divergiu do SHA-256 imutável: esperado={politica.holdout_sha256} atual={sha256}'
        )
    return sha256


def _contem_pii(texto: str) -> bool:
    return any(padrao.search(texto) for padrao in _PADROES_PII)


def carregar_amostras_observadas(caminho: Path) -> list[RegistroObservadoML]:
    registros: list[RegistroObservadoML] = []
    ids: set[str] = set()
    for numero_linha, linha in enumerate(caminho.read_text(encoding='utf-8').splitlines(), start=1):
        if not linha.strip():
            continue
        item = json.loads(linha)
        registro = RegistroObservadoML(
            id=str(item['id']).strip(),
            texto=str(item['texto']).strip(),
            source_ref=str(item['source_ref']).strip(),
            categoria_sugerida=str(item['categoria_sugerida']).strip(),
            anonimizado=bool(item['anonimizado']),
            revisao_status=str(item['revisao_status']).strip(),
            categoria_revisada=(str(item['categoria_revisada']).strip() if item.get('categoria_revisada') else None),
            revisor_ref=(str(item['revisor_ref']).strip() if item.get('revisor_ref') else None),
        )
        if not registro.id or not registro.texto or not registro.source_ref:
            raise ValueError(f'amostra observada inválida na linha {numero_linha}')
        if registro.id in ids:
            raise ValueError(f'id duplicado nas amostras observadas: {registro.id}')
        if registro.categoria_sugerida not in CATEGORIAS:
            raise ValueError(f'categoria_sugerida desconhecida: {registro.categoria_sugerida}')
        if registro.revisao_status not in STATUS_REVISAO:
            raise ValueError(f'revisao_status inválido: {registro.revisao_status}')
        if not registro.anonimizado or _contem_pii(registro.texto):
            raise ValueError(f'amostra não anonimizada ou com PII detectável: {registro.id}')
        if registro.revisao_status == 'APROVADO':
            if registro.categoria_revisada not in CATEGORIAS or not registro.revisor_ref:
                raise ValueError(f'amostra aprovada sem revisão completa: {registro.id}')
        ids.add(registro.id)
        registros.append(registro)
    return registros


def amostras_aprovadas_para_treino(registros: Iterable[RegistroObservadoML]) -> list[RegistroTreinoML]:
    return [
        RegistroTreinoML(texto=item.texto, categoria=item.categoria_revisada or item.categoria_sugerida)
        for item in registros
        if item.revisao_status == 'APROVADO'
    ]


def treinar_modelo_runtime(dataset_p2: Path) -> ClassificadorRequisitoSupervisionado:
    registros, _ = carregar_dataset_ml(dataset_p2)
    treino = [item for item in registros if item.split == 'treino']
    return ClassificadorRequisitoSupervisionado().treinar(
        RegistroTreinoML(texto=item.texto, categoria=item.categoria) for item in treino
    )


def avaliar_holdout(
    modelo: ClassificadorRequisitoSupervisionado,
    holdout: Sequence[RegistroHoldoutML],
    *,
    holdout_sha256: str,
    politica: PoliticaRuntimeML,
) -> ResultadoHoldoutML:
    y_true = [item.categoria for item in holdout]
    y_baseline = [classificar_requisito(item.texto).categoria for item in holdout]
    y_modelo = [modelo.classificar(item.texto).categoria for item in holdout]
    baseline = avaliar_classificador(y_true, y_baseline)
    metricas_modelo = avaliar_classificador(y_true, y_modelo)
    ganho = round(metricas_modelo.macro_f1 - baseline.macro_f1, 4)
    criterios = {
        'sha_holdout_imutavel': holdout_sha256 == politica.holdout_sha256,
        'macro_f1_holdout_minimo': metricas_modelo.macro_f1 >= politica.macro_f1_holdout_minimo,
        'ganho_sobre_baseline': ganho >= politica.ganho_f1_holdout_minimo,
        'modelo_supera_baseline': metricas_modelo.macro_f1 > baseline.macro_f1,
    }
    return ResultadoHoldoutML(
        holdout_sha256=holdout_sha256,
        quantidade=len(holdout),
        baseline_macro_f1=baseline.macro_f1,
        modelo_macro_f1=metricas_modelo.macro_f1,
        ganho_macro_f1=ganho,
        status='APROVADO' if all(criterios.values()) else 'BLOQUEADO',
        criterios=criterios,
    )


def _selecionado_canario(correlation_id: str, percentual: float) -> bool:
    if percentual <= 0:
        return False
    if percentual >= 100:
        return True
    digest = hashlib.sha256(correlation_id.encode('utf-8')).digest()
    bucket = int.from_bytes(digest[:8], 'big') / float(2**64)
    return bucket < percentual / 100.0


def classificar_runtime(
    texto: str,
    *,
    correlation_id: str,
    politica: PoliticaRuntimeML,
    modelo: ClassificadorRequisitoSupervisionado,
    modo: str | None = None,
) -> DecisaoRuntimeML:
    if not correlation_id.strip():
        raise ValueError('correlation_id é obrigatório')
    modo_efetivo = (modo or politica.modo_padrao).lower()
    if modo_efetivo not in MODOS_RUNTIME:
        raise ValueError(f'modo de runtime inválido: {modo_efetivo}')

    baseline = classificar_requisito(texto)
    if modo_efetivo == 'off':
        return DecisaoRuntimeML(
            categoria=baseline.categoria,
            confianca=baseline.confianca,
            engine=baseline.baseline,
            modo=modo_efetivo,
            correlation_id=correlation_id,
            modelo_categoria=None,
            modelo_confianca=None,
            baseline_categoria=baseline.categoria,
            canary_selected=False,
            fallback_reason='ML_OFF',
            evidencias=baseline.evidencias,
        )

    try:
        predicao = modelo.classificar(texto)
    except Exception as exc:
        return DecisaoRuntimeML(
            categoria=baseline.categoria,
            confianca=baseline.confianca,
            engine=baseline.baseline,
            modo=modo_efetivo,
            correlation_id=correlation_id,
            modelo_categoria=None,
            modelo_confianca=None,
            baseline_categoria=baseline.categoria,
            canary_selected=False,
            fallback_reason=f'ML_RUNTIME_ERROR:{type(exc).__name__}',
            evidencias=baseline.evidencias,
        )

    selecionado = modo_efetivo == 'active' or (
        modo_efetivo == 'canary'
        and _selecionado_canario(correlation_id, politica.canary_percentual)
    )
    confiavel = predicao.confianca >= politica.confianca_minima_modelo

    if modo_efetivo == 'shadow':
        usar_modelo = False
        fallback_reason = 'SHADOW_ONLY'
    elif not selecionado:
        usar_modelo = False
        fallback_reason = 'CANARY_NOT_SELECTED'
    elif not confiavel:
        usar_modelo = False
        fallback_reason = 'LOW_CONFIDENCE'
    else:
        usar_modelo = True
        fallback_reason = None

    return DecisaoRuntimeML(
        categoria=predicao.categoria if usar_modelo else baseline.categoria,
        confianca=predicao.confianca if usar_modelo else baseline.confianca,
        engine=predicao.modelo if usar_modelo else baseline.baseline,
        modo=modo_efetivo,
        correlation_id=correlation_id,
        modelo_categoria=predicao.categoria,
        modelo_confianca=predicao.confianca,
        baseline_categoria=baseline.categoria,
        canary_selected=selecionado,
        fallback_reason=fallback_reason,
        evidencias=predicao.evidencias if usar_modelo else baseline.evidencias,
    )


def _js_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    m = {categoria: (p[categoria] + q[categoria]) / 2 for categoria in CATEGORIAS}

    def kl(a: dict[str, float], b: dict[str, float]) -> float:
        total = 0.0
        for categoria in CATEGORIAS:
            if a[categoria] > 0:
                total += a[categoria] * math.log2(a[categoria] / b[categoria])
        return total

    return (kl(p, m) + kl(q, m)) / 2


def calcular_drift(
    eventos: Sequence[EventoClassificacaoML],
    *,
    politica: PoliticaRuntimeML,
) -> ResultadoDriftML:
    if not eventos:
        raise ValueError('ao menos um evento é obrigatório para medir drift')
    desconhecidas = {evento.categoria for evento in eventos} - set(CATEGORIAS)
    if desconhecidas:
        raise ValueError(f'categorias desconhecidas nos eventos: {sorted(desconhecidas)}')
    contagem = Counter(evento.categoria for evento in eventos)
    total = len(eventos)
    observada = {categoria: contagem[categoria] / total for categoria in CATEGORIAS}
    referencia = politica.distribuicao_referencia
    js = round(_js_divergence(observada, referencia), 4)
    baixa_confianca = sum(
        1 for evento in eventos if evento.confianca < politica.confianca_minima_modelo
    ) / total
    taxa_baixa = round(baixa_confianca, 4)
    delta = {
        categoria: round(observada[categoria] - referencia[categoria], 4)
        for categoria in CATEGORIAS
    }
    alertas: list[str] = []
    if js >= politica.js_divergence_alerta:
        alertas.append('CATEGORY_DISTRIBUTION_DRIFT')
    if taxa_baixa >= politica.taxa_baixa_confianca_alerta:
        alertas.append('LOW_CONFIDENCE_RATE')
    return ResultadoDriftML(
        total=total,
        js_divergence=js,
        taxa_baixa_confianca=taxa_baixa,
        distribuicao_observada={k: round(v, 4) for k, v in observada.items()},
        delta_por_categoria=delta,
        alertas=alertas,
    )
