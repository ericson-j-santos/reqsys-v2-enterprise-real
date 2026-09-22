from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from app.services.requisito_classifier import (
    CATEGORIAS,
    MetricasClassificacao,
    avaliar_classificador,
    classificar_requisito,
)

MODELO_VERSAO = 'multinomial-nb-word-char-ngram-v1'
SPLITS_VALIDOS = ('treino', 'validacao')


@dataclass(frozen=True)
class RegistroTreinoML:
    texto: str
    categoria: str


@dataclass(frozen=True)
class RegistroDatasetML:
    id: str
    texto: str
    categoria: str
    split: str
    origem: str
    dataset_versao: str


@dataclass(frozen=True)
class PredicaoRequisitoML:
    categoria: str
    confianca: float
    probabilidades: dict[str, float]
    evidencias: list[str]
    modelo: str = MODELO_VERSAO


@dataclass(frozen=True)
class PoliticaPromocaoML:
    versao: str
    dataset_versao: str
    modelo_versao: str
    macro_f1_minimo: float
    ganho_macro_f1_minimo: float
    minimo_treino_por_categoria: int
    minimo_validacao_por_categoria: int


@dataclass(frozen=True)
class ResultadoPromocaoML:
    status: str
    politica: PoliticaPromocaoML
    dataset_sha256: str
    quantidade_treino: int
    quantidade_validacao: int
    baseline: MetricasClassificacao
    modelo: MetricasClassificacao
    ganho_macro_f1: float
    criterios: dict[str, bool]

    def como_dict(self) -> dict:
        return asdict(self)


def _normalizar(texto: str) -> list[str]:
    return re.findall(r'[a-zA-ZÀ-ÿ0-9_]+', texto.lower())


def _extrair_features(texto: str) -> list[str]:
    termos = _normalizar(texto)
    features = [f'w1:{termo}' for termo in termos]
    features.extend(
        f'w2:{atual}__{proximo}'
        for atual, proximo in zip(termos, termos[1:], strict=False)
    )

    texto_normalizado = f" {' '.join(termos)} "
    for tamanho in (3, 4, 5):
        features.extend(
            f'c{tamanho}:{texto_normalizado[indice:indice + tamanho]}'
            for indice in range(max(0, len(texto_normalizado) - tamanho + 1))
        )
    return features


class ClassificadorRequisitoSupervisionado:
    def __init__(
        self,
        *,
        categorias: Sequence[str] = CATEGORIAS,
        alpha: float = 1.0,
    ) -> None:
        if alpha <= 0:
            raise ValueError('alpha deve ser maior que zero')
        if not categorias:
            raise ValueError('ao menos uma categoria é obrigatória')

        self.categorias = tuple(categorias)
        self.alpha = float(alpha)
        self._documentos_por_categoria: Counter[str] = Counter()
        self._features_por_categoria: dict[str, Counter[str]] = {
            categoria: Counter() for categoria in self.categorias
        }
        self._total_features_por_categoria: Counter[str] = Counter()
        self._vocabulario: set[str] = set()
        self._total_documentos = 0
        self._treinado = False

    def treinar(self, registros: Iterable[RegistroTreinoML]) -> 'ClassificadorRequisitoSupervisionado':
        documentos = list(registros)
        if not documentos:
            raise ValueError('dataset de treino não pode ser vazio')

        desconhecidas = {
            registro.categoria
            for registro in documentos
            if registro.categoria not in self.categorias
        }
        if desconhecidas:
            raise ValueError(f'categorias de treino desconhecidas: {sorted(desconhecidas)}')

        vazios = [registro for registro in documentos if not registro.texto.strip()]
        if vazios:
            raise ValueError('texto de treino não pode ser vazio')

        suporte = Counter(registro.categoria for registro in documentos)
        ausentes = [categoria for categoria in self.categorias if suporte[categoria] == 0]
        if ausentes:
            raise ValueError(f'categorias sem exemplos de treino: {ausentes}')

        self._documentos_por_categoria = Counter()
        self._features_por_categoria = {
            categoria: Counter() for categoria in self.categorias
        }
        self._total_features_por_categoria = Counter()
        self._vocabulario = set()
        self._total_documentos = len(documentos)

        for registro in documentos:
            self._documentos_por_categoria[registro.categoria] += 1
            contagem = Counter(_extrair_features(registro.texto))
            self._features_por_categoria[registro.categoria].update(contagem)
            self._total_features_por_categoria[registro.categoria] += sum(contagem.values())
            self._vocabulario.update(contagem)

        self._treinado = True
        return self

    def classificar(self, texto: str) -> PredicaoRequisitoML:
        if not self._treinado:
            raise RuntimeError('modelo ainda não foi treinado')
        if not texto or not texto.strip():
            raise ValueError('texto do requisito é obrigatório')

        features = Counter(_extrair_features(texto))
        tamanho_vocabulario = len(self._vocabulario)
        scores_log: dict[str, float] = {}

        for categoria in self.categorias:
            documentos_categoria = self._documentos_por_categoria[categoria]
            prior = documentos_categoria / self._total_documentos
            score = math.log(prior)

            denominador = (
                self._total_features_por_categoria[categoria]
                + self.alpha * tamanho_vocabulario
            )
            frequencias = self._features_por_categoria[categoria]

            for feature, ocorrencias in features.items():
                if feature not in self._vocabulario:
                    continue
                probabilidade = (
                    frequencias[feature] + self.alpha
                ) / denominador
                score += ocorrencias * math.log(probabilidade)

            scores_log[categoria] = score

        maior_log = max(scores_log.values())
        exponenciais = {
            categoria: math.exp(score - maior_log)
            for categoria, score in scores_log.items()
        }
        total = sum(exponenciais.values())
        probabilidades = {
            categoria: valor / total
            for categoria, valor in exponenciais.items()
        }
        categoria = max(self.categorias, key=lambda item: probabilidades[item])

        frequencias_categoria = self._features_por_categoria[categoria]
        evidencias = sorted(
            (
                feature
                for feature in features
                if feature in self._vocabulario and frequencias_categoria[feature] > 0
            ),
            key=lambda feature: (
                frequencias_categoria[feature],
                features[feature],
                feature,
            ),
            reverse=True,
        )[:8]

        return PredicaoRequisitoML(
            categoria=categoria,
            confianca=round(probabilidades[categoria], 4),
            probabilidades={
                chave: round(valor, 4)
                for chave, valor in probabilidades.items()
            },
            evidencias=evidencias,
        )

    def exportar_estado(self) -> dict:
        if not self._treinado:
            raise RuntimeError('modelo ainda não foi treinado')

        return {
            'modelo_versao': MODELO_VERSAO,
            'categorias': list(self.categorias),
            'alpha': self.alpha,
            'total_documentos': self._total_documentos,
            'documentos_por_categoria': dict(self._documentos_por_categoria),
            'total_features_por_categoria': dict(self._total_features_por_categoria),
            'features_por_categoria': {
                categoria: dict(sorted(self._features_por_categoria[categoria].items()))
                for categoria in self.categorias
            },
        }


def carregar_dataset_ml(caminho: Path) -> tuple[list[RegistroDatasetML], str]:
    conteudo = caminho.read_bytes()
    sha256 = hashlib.sha256(conteudo).hexdigest()

    registros: list[RegistroDatasetML] = []
    ids: set[str] = set()

    for numero_linha, linha_bytes in enumerate(conteudo.splitlines(), start=1):
        if not linha_bytes.strip():
            continue
        try:
            item = json.loads(linha_bytes.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f'dataset inválido na linha {numero_linha}: {exc}') from exc

        obrigatorios = {'id', 'texto', 'categoria', 'split', 'origem', 'dataset_versao'}
        ausentes = obrigatorios - set(item)
        if ausentes:
            raise ValueError(
                f'dataset inválido na linha {numero_linha}; campos ausentes: {sorted(ausentes)}'
            )

        registro = RegistroDatasetML(
            id=str(item['id']).strip(),
            texto=str(item['texto']).strip(),
            categoria=str(item['categoria']).strip(),
            split=str(item['split']).strip(),
            origem=str(item['origem']).strip(),
            dataset_versao=str(item['dataset_versao']).strip(),
        )

        if not registro.id or not registro.texto or not registro.origem or not registro.dataset_versao:
            raise ValueError(f'dataset inválido na linha {numero_linha}; valores vazios')
        if registro.id in ids:
            raise ValueError(f'id duplicado no dataset: {registro.id}')
        if registro.categoria not in CATEGORIAS:
            raise ValueError(f'categoria desconhecida no dataset: {registro.categoria}')
        if registro.split not in SPLITS_VALIDOS:
            raise ValueError(f'split desconhecido no dataset: {registro.split}')

        ids.add(registro.id)
        registros.append(registro)

    if not registros:
        raise ValueError('dataset versionado não pode ser vazio')

    versoes = {registro.dataset_versao for registro in registros}
    if len(versoes) != 1:
        raise ValueError(f'dataset contém versões inconsistentes: {sorted(versoes)}')

    return registros, sha256


def carregar_politica_ml(caminho: Path) -> PoliticaPromocaoML:
    item = json.loads(caminho.read_text(encoding='utf-8'))
    politica = PoliticaPromocaoML(
        versao=str(item['versao']),
        dataset_versao=str(item['dataset_versao']),
        modelo_versao=str(item['modelo_versao']),
        macro_f1_minimo=float(item['macro_f1_minimo']),
        ganho_macro_f1_minimo=float(item['ganho_macro_f1_minimo']),
        minimo_treino_por_categoria=int(item['minimo_treino_por_categoria']),
        minimo_validacao_por_categoria=int(item['minimo_validacao_por_categoria']),
    )

    if politica.modelo_versao != MODELO_VERSAO:
        raise ValueError(
            f'política exige modelo {politica.modelo_versao}, '
            f'mas o runtime fornece {MODELO_VERSAO}'
        )
    if not 0 <= politica.macro_f1_minimo <= 1:
        raise ValueError('macro_f1_minimo deve estar entre 0 e 1')
    if politica.ganho_macro_f1_minimo < 0:
        raise ValueError('ganho_macro_f1_minimo não pode ser negativo')
    if politica.minimo_treino_por_categoria < 1:
        raise ValueError('minimo_treino_por_categoria deve ser maior que zero')
    if politica.minimo_validacao_por_categoria < 1:
        raise ValueError('minimo_validacao_por_categoria deve ser maior que zero')

    return politica


def avaliar_promocao_ml(
    registros: Sequence[RegistroDatasetML],
    *,
    dataset_sha256: str,
    politica: PoliticaPromocaoML,
) -> tuple[ResultadoPromocaoML, ClassificadorRequisitoSupervisionado]:
    versoes_dataset = {registro.dataset_versao for registro in registros}
    if versoes_dataset != {politica.dataset_versao}:
        raise ValueError(
            f'política exige dataset {politica.dataset_versao}, '
            f'mas foram recebidas versões {sorted(versoes_dataset)}'
        )

    treino = [registro for registro in registros if registro.split == 'treino']
    validacao = [registro for registro in registros if registro.split == 'validacao']

    suporte_treino = Counter(registro.categoria for registro in treino)
    suporte_validacao = Counter(registro.categoria for registro in validacao)

    insuficientes_treino = {
        categoria: suporte_treino[categoria]
        for categoria in CATEGORIAS
        if suporte_treino[categoria] < politica.minimo_treino_por_categoria
    }
    insuficientes_validacao = {
        categoria: suporte_validacao[categoria]
        for categoria in CATEGORIAS
        if suporte_validacao[categoria] < politica.minimo_validacao_por_categoria
    }
    if insuficientes_treino:
        raise ValueError(f'suporte de treino insuficiente: {insuficientes_treino}')
    if insuficientes_validacao:
        raise ValueError(f'suporte de validação insuficiente: {insuficientes_validacao}')

    modelo = ClassificadorRequisitoSupervisionado().treinar(
        RegistroTreinoML(texto=item.texto, categoria=item.categoria)
        for item in treino
    )

    y_true = [item.categoria for item in validacao]
    y_pred_baseline = [classificar_requisito(item.texto).categoria for item in validacao]
    y_pred_modelo = [modelo.classificar(item.texto).categoria for item in validacao]

    metricas_baseline = avaliar_classificador(y_true, y_pred_baseline)
    metricas_modelo = avaliar_classificador(y_true, y_pred_modelo)
    ganho = round(metricas_modelo.macro_f1 - metricas_baseline.macro_f1, 4)

    criterios = {
        'macro_f1_minimo': metricas_modelo.macro_f1 >= politica.macro_f1_minimo,
        'ganho_sobre_baseline': ganho >= politica.ganho_macro_f1_minimo,
        'modelo_supera_baseline': metricas_modelo.macro_f1 > metricas_baseline.macro_f1,
    }
    status = 'APROVADO' if all(criterios.values()) else 'BLOQUEADO'

    return (
        ResultadoPromocaoML(
            status=status,
            politica=politica,
            dataset_sha256=dataset_sha256,
            quantidade_treino=len(treino),
            quantidade_validacao=len(validacao),
            baseline=metricas_baseline,
            modelo=metricas_modelo,
            ganho_macro_f1=ganho,
            criterios=criterios,
        ),
        modelo,
    )
