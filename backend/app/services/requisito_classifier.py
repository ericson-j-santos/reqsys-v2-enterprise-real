from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

CATEGORIAS = (
    'FUNCIONAL',
    'NAO_FUNCIONAL',
    'SEGURANCA',
    'INTEGRACAO',
    'DADOS',
    'UX',
    'OPERACIONAL',
)

PALAVRAS_CHAVE: dict[str, tuple[str, ...]] = {
    'SEGURANCA': ('autenticação', 'autenticacao', 'autorização', 'autorizacao', 'permissão', 'permissao', 'token', 'segredo', 'lgpd', 'criptografia', 'auditoria', 'mfa'),
    'INTEGRACAO': ('api', 'integração', 'integracao', 'webhook', 'endpoint', 'fila', 'mensageria', 'rest', 'soap', 'conector'),
    'DADOS': ('banco', 'sql', 'tabela', 'campo', 'dado', 'dados', 'etl', 'relatório', 'relatorio', 'dashboard', 'persistir', 'armazenar'),
    'UX': ('tela', 'interface', 'botão', 'botao', 'layout', 'acessibilidade', 'responsivo', 'formulário', 'formulario', 'usuário', 'usuario'),
    'OPERACIONAL': ('deploy', 'rollback', 'monitoramento', 'observabilidade', 'alerta', 'health', 'runbook', 'backup', 'restauração', 'restauracao'),
    'NAO_FUNCIONAL': ('desempenho', 'performance', 'latência', 'latencia', 'disponibilidade', 'escalabilidade', 'resiliência', 'resiliencia', 'sla', 'timeout'),
    'FUNCIONAL': ('deve', 'permitir', 'cadastrar', 'consultar', 'alterar', 'excluir', 'aprovar', 'rejeitar', 'calcular', 'emitir', 'gerar'),
}

# Verbos funcionais como "deve" e "permitir" aparecem também em requisitos
# de segurança, desempenho, UX e operação. Eles são sinais genéricos e, por
# isso, não podem empatar com um sinal específico de domínio como "latência".
PESO_CATEGORIA: dict[str, float] = {
    'FUNCIONAL': 0.5,
    'NAO_FUNCIONAL': 1.0,
    'SEGURANCA': 1.0,
    'INTEGRACAO': 1.0,
    'DADOS': 1.0,
    'UX': 1.0,
    'OPERACIONAL': 1.0,
}


@dataclass(frozen=True)
class ClassificacaoRequisito:
    categoria: str
    confianca: float
    scores: dict[str, float]
    evidencias: list[str]
    baseline: str = 'keyword-weighted-v1'


@dataclass(frozen=True)
class MetricasClassificacao:
    acuracia: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    matriz_confusao: dict[str, dict[str, int]]
    suporte: dict[str, int]


def _normalizar(texto: str) -> list[str]:
    return re.findall(r'[a-zA-ZÀ-ÿ0-9_]+', texto.lower())


def classificar_requisito(texto: str) -> ClassificacaoRequisito:
    if not texto or not texto.strip():
        raise ValueError('texto do requisito é obrigatório')

    termos = _normalizar(texto)
    contagem = Counter(termos)
    scores: dict[str, float] = {}
    evidencias_por_categoria: dict[str, list[str]] = {}

    for categoria in CATEGORIAS:
        evidencias: list[str] = []
        score = 0.0
        peso = PESO_CATEGORIA[categoria]
        for palavra in PALAVRAS_CHAVE[categoria]:
            ocorrencias = contagem.get(palavra, 0)
            if ocorrencias:
                evidencias.append(palavra)
                score += float(ocorrencias) * peso
        scores[categoria] = score
        evidencias_por_categoria[categoria] = evidencias

    maior_score = max(scores.values())
    if maior_score <= 0:
        categoria = 'FUNCIONAL'
        confianca = 0.25
        evidencias = []
    else:
        empatadas = [c for c in CATEGORIAS if scores[c] == maior_score]
        categoria = empatadas[0]
        total = sum(scores.values())
        confianca = maior_score / total if total else 0.0
        evidencias = evidencias_por_categoria[categoria]

    return ClassificacaoRequisito(
        categoria=categoria,
        confianca=round(confianca, 4),
        scores={categoria: round(valor, 4) for categoria, valor in scores.items()},
        evidencias=evidencias,
    )


def avaliar_classificador(
    y_true: Iterable[str],
    y_pred: Iterable[str],
    *,
    categorias: Iterable[str] = CATEGORIAS,
) -> MetricasClassificacao:
    verdade = list(y_true)
    previsto = list(y_pred)
    labels = list(categorias)

    if len(verdade) != len(previsto):
        raise ValueError('y_true e y_pred devem possuir o mesmo tamanho')
    if not verdade:
        raise ValueError('é necessário ao menos um exemplo para avaliação')

    desconhecidas = (set(verdade) | set(previsto)) - set(labels)
    if desconhecidas:
        raise ValueError(f'categorias desconhecidas: {sorted(desconhecidas)}')

    matriz = {real: {pred: 0 for pred in labels} for real in labels}
    suporte = {label: 0 for label in labels}

    for real, pred in zip(verdade, previsto, strict=True):
        matriz[real][pred] += 1
        suporte[real] += 1

    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []

    for label in labels:
        tp = matriz[label][label]
        fp = sum(matriz[real][label] for real in labels if real != label)
        fn = sum(matriz[label][pred] for pred in labels if pred != label)

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        if suporte[label] > 0:
            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)

    acertos = sum(matriz[label][label] for label in labels)
    total = len(verdade)

    return MetricasClassificacao(
        acuracia=round(acertos / total, 4),
        macro_precision=round(sum(precisions) / len(precisions), 4) if precisions else 0.0,
        macro_recall=round(sum(recalls) / len(recalls), 4) if recalls else 0.0,
        macro_f1=round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        matriz_confusao=matriz,
        suporte=suporte,
    )
