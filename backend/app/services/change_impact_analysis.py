"""Experimento governado de análise de impacto de CHANGE.

O módulo compara rastreabilidade em grafo, recuperação semântica e um caminho
híbrido RAG + LLM. O LLM nunca cria evidência canônica: ele apenas seleciona,
classifica e explica artefatos previamente recuperados.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.ai_provider_router import AIProviderRouter
from app.services.rag_governado import DocumentoRAG, recuperar_fontes_semanticas

LlmGenerate = Callable[[str, str], str]


class ImpactChange(Protocol):
    change_id: str
    query: str
    seed_artifact_ids: tuple[str, ...]


class ChangeImpactValidationError(ValueError):
    """Entrada ou saída inválida do experimento de impacto."""


@dataclass(frozen=True, slots=True)
class ImpactArtifact:
    artifact_id: str
    kind: str
    text: str
    source_uri: str
    links: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("artifact_id", "kind", "text", "source_uri"):
            if not str(getattr(self, field_name)).strip():
                raise ChangeImpactValidationError(f"{field_name} deve ser informado")
        object.__setattr__(
            self,
            "links",
            tuple(dict.fromkeys(str(item).strip() for item in self.links if str(item).strip())),
        )
        if self.artifact_id in self.links:
            raise ChangeImpactValidationError("artefato não pode apontar para si mesmo")


@dataclass(frozen=True, slots=True)
class HistoricalChange:
    change_id: str
    query: str
    seed_artifact_ids: tuple[str, ...]
    ground_truth: frozenset[str]

    def __post_init__(self) -> None:
        if not self.change_id.strip() or not self.query.strip():
            raise ChangeImpactValidationError("change_id e query devem ser informados")
        seeds = tuple(
            dict.fromkeys(str(item).strip() for item in self.seed_artifact_ids if str(item).strip())
        )
        truth = frozenset(str(item).strip() for item in self.ground_truth if str(item).strip())
        if not seeds:
            raise ChangeImpactValidationError("ao menos um seed_artifact_id é obrigatório")
        if not truth:
            raise ChangeImpactValidationError("ground_truth não pode ser vazio")
        object.__setattr__(self, "seed_artifact_ids", seeds)
        object.__setattr__(self, "ground_truth", truth)


@dataclass(frozen=True, slots=True)
class LiveChange:
    """Mudança operacional avaliada sobre a rastreabilidade viva."""

    change_id: str
    query: str
    seed_artifact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.change_id.strip() or not self.query.strip():
            raise ChangeImpactValidationError("change_id e query devem ser informados")
        seeds = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in self.seed_artifact_ids
                if str(item).strip()
            )
        )
        if not seeds:
            raise ChangeImpactValidationError("ao menos um seed_artifact_id é obrigatório")
        object.__setattr__(self, "seed_artifact_ids", seeds)


@dataclass(frozen=True, slots=True)
class ImpactCandidate:
    artifact_id: str
    relation: str
    confidence: float
    evidence: tuple[str, ...]
    reason: str
    strategy: str

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ChangeImpactValidationError("confidence deve estar entre 0 e 1")
        if not self.evidence:
            raise ChangeImpactValidationError("candidate exige evidência de recuperação")


@dataclass(frozen=True, slots=True)
class StrategyResult:
    strategy: str
    candidates: tuple[ImpactCandidate, ...]
    llm_status: str = "not_applicable"
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    strategy: str
    retrieved: int
    true_positives: int
    recall: float
    precision: float
    review_rate: float
    llm_status: str


def _artifact_map(artifacts: Iterable[ImpactArtifact]) -> dict[str, ImpactArtifact]:
    mapped: dict[str, ImpactArtifact] = {}
    for artifact in artifacts:
        if artifact.artifact_id in mapped:
            raise ChangeImpactValidationError(f"artifact_id duplicado: {artifact.artifact_id}")
        mapped[artifact.artifact_id] = artifact
    return mapped


def validate_dataset(
    artifacts: Iterable[ImpactArtifact],
    changes: Iterable[HistoricalChange],
) -> tuple[tuple[ImpactArtifact, ...], tuple[HistoricalChange, ...]]:
    artifact_tuple = tuple(artifacts)
    change_tuple = tuple(changes)
    mapped = _artifact_map(artifact_tuple)
    known = set(mapped)
    for artifact in artifact_tuple:
        missing_links = sorted(set(artifact.links) - known)
        if missing_links:
            raise ChangeImpactValidationError(
                f"{artifact.artifact_id} possui links inexistentes: {', '.join(missing_links)}"
            )
    for change in change_tuple:
        missing_seeds = sorted(set(change.seed_artifact_ids) - known)
        missing_truth = sorted(set(change.ground_truth) - known)
        if missing_seeds or missing_truth:
            raise ChangeImpactValidationError(
                f"{change.change_id} referencia artefatos inexistentes: "
                f"seeds={missing_seeds}; ground_truth={missing_truth}"
            )
    return artifact_tuple, change_tuple


def _traceability_graph_uri(graph: dict[str, Any]) -> str:
    requirement = graph.get("requirement")
    if not isinstance(requirement, dict):
        raise ChangeImpactValidationError("grafo sem requirement válido")
    requirement_id = requirement.get("id")
    if requirement_id is None:
        raise ChangeImpactValidationError("grafo sem requirement.id")
    return f"/v1/rastreabilidade/requisitos/{requirement_id}/grafo"


def artifacts_from_traceability_graph(
    graph: dict[str, Any],
    *,
    include_rejected_evidence: bool = False,
) -> tuple[ImpactArtifact, ...]:
    """Converte o grafo vivo em artefatos consumíveis pelo Impact Engine.

    Por padrão, arestas rejeitadas ficam fora do conjunto operacional para que
    evidência inválida continue diagnosticável no grafo sem validar impacto.
    """

    if graph.get("graph_type") != "functional_traceability_graph":
        raise ChangeImpactValidationError("graph_type incompatível")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ChangeImpactValidationError("grafo exige nodes[] e edges[]")

    node_map: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ChangeImpactValidationError("node inválido no grafo")
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            raise ChangeImpactValidationError("node sem id")
        if node_id in node_map:
            raise ChangeImpactValidationError(f"node id duplicado: {node_id}")
        node_map[node_id] = node

    links_by_source: dict[str, list[str]] = {node_id: [] for node_id in node_map}
    included_ids: set[str] = set()
    accepted_statuses = {"reference", "verified"}
    if include_rejected_evidence:
        accepted_statuses.add("rejected")

    for edge in edges:
        if not isinstance(edge, dict):
            raise ChangeImpactValidationError("edge inválida no grafo")
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        relation = str(edge.get("relation") or "").strip()
        status = str(edge.get("evidence_status") or "").strip().lower()
        if not source or not target or not relation:
            raise ChangeImpactValidationError("edge sem source, target ou relation")
        if source not in node_map or target not in node_map:
            raise ChangeImpactValidationError(
                f"edge referencia node inexistente: {source}->{target}"
            )
        if status not in {"reference", "verified", "rejected"}:
            raise ChangeImpactValidationError(
                f"evidence_status inválido: {status or 'missing'}"
            )
        if status not in accepted_statuses:
            continue
        included_ids.update((source, target))
        links_by_source[source].append(target)

    requirement = graph.get("requirement") or {}
    requirement_code = str(requirement.get("code") or "").strip()
    requirement_node_id = f"requirement:{requirement_code}" if requirement_code else ""
    if requirement_node_id in node_map:
        included_ids.add(requirement_node_id)

    graph_uri = _traceability_graph_uri(graph)
    artifacts: list[ImpactArtifact] = []
    for node_id in sorted(included_ids):
        node = node_map[node_id]
        metadata = node.get("metadata")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ChangeImpactValidationError(f"metadata inválido em {node_id}")
        kind = str(node.get("type") or "").strip()
        label = str(node.get("label") or "").strip()
        if not kind or not label:
            raise ChangeImpactValidationError(f"node incompleto: {node_id}")
        source_uri = str(node.get("source_uri") or "").strip() or graph_uri
        text = json.dumps(
            {
                "id": node_id,
                "type": kind,
                "label": label,
                "metadata": metadata,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        artifacts.append(
            ImpactArtifact(
                artifact_id=node_id,
                kind=kind,
                text=text,
                source_uri=source_uri,
                links=tuple(sorted(set(links_by_source[node_id]))),
            )
        )
    if not artifacts:
        raise ChangeImpactValidationError("grafo não possui rastreabilidade elegível")
    return tuple(artifacts)


def analyze_live_change(
    graph: dict[str, Any],
    *,
    change_id: str,
    query: str,
    llm_generate: LlmGenerate | None,
    seed_artifact_ids: Iterable[str] | None = None,
    graph_depth: int = 2,
    semantic_top_k: int = 6,
    correlation_id: str | None = None,
) -> tuple[StrategyResult, StrategyResult, StrategyResult]:
    """Executa análise de impacto usando apenas candidatos do grafo vivo."""

    artifacts = artifacts_from_traceability_graph(graph)
    known = {artifact.artifact_id for artifact in artifacts}

    if seed_artifact_ids is None:
        requirement = graph.get("requirement") or {}
        requirement_code = str(requirement.get("code") or "").strip()
        seeds = (f"requirement:{requirement_code}",) if requirement_code else ()
    else:
        seeds = tuple(seed_artifact_ids)

    change = LiveChange(
        change_id=change_id,
        query=query,
        seed_artifact_ids=seeds,
    )
    missing_seeds = sorted(set(change.seed_artifact_ids) - known)
    if missing_seeds:
        raise ChangeImpactValidationError(
            "seeds ausentes da rastreabilidade viva: " + ", ".join(missing_seeds)
        )

    return (
        graph_candidates(change, artifacts, max_depth=graph_depth),
        semantic_candidates(change, artifacts, top_k=semantic_top_k),
        hybrid_candidates(
            change,
            artifacts,
            llm_generate=llm_generate,
            graph_depth=graph_depth,
            semantic_top_k=semantic_top_k,
            correlation_id=correlation_id,
        ),
    )


def graph_candidates(
    change: ImpactChange,
    artifacts: Iterable[ImpactArtifact],
    *,
    max_depth: int = 2,
) -> StrategyResult:
    if max_depth < 1:
        raise ChangeImpactValidationError("max_depth deve ser >= 1")
    mapped = _artifact_map(artifacts)
    seeds = set(change.seed_artifact_ids)
    queue = deque((seed, 0) for seed in change.seed_artifact_ids)
    visited = set(seeds)
    distances: dict[str, int] = {}

    while queue:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for linked in mapped[current].links:
            if linked in visited:
                continue
            visited.add(linked)
            distances[linked] = depth + 1
            queue.append((linked, depth + 1))

    candidates = []
    for artifact_id, distance in sorted(distances.items(), key=lambda item: (item[1], item[0])):
        artifact = mapped[artifact_id]
        confidence = max(0.2, 1.0 - (distance - 1) * 0.25)
        candidates.append(
            ImpactCandidate(
                artifact_id=artifact_id,
                relation=f"GRAPH_DEPTH_{distance}",
                confidence=confidence,
                evidence=(artifact.source_uri, f"graph_distance={distance}"),
                reason=f"Artefato alcançado por rastreabilidade explícita em {distance} salto(s).",
                strategy="graph",
            )
        )
    return StrategyResult(strategy="graph", candidates=tuple(candidates))


def semantic_candidates(
    change: ImpactChange,
    artifacts: Iterable[ImpactArtifact],
    *,
    top_k: int = 6,
) -> StrategyResult:
    if top_k < 1:
        raise ChangeImpactValidationError("top_k deve ser >= 1")
    artifact_tuple = tuple(artifacts)
    seeds = set(change.seed_artifact_ids)
    documents = [
        DocumentoRAG(
            id=artifact.artifact_id,
            titulo=f"{artifact.kind}: {artifact.artifact_id}",
            conteudo=artifact.text,
            origem=artifact.source_uri,
        )
        for artifact in artifact_tuple
        if artifact.artifact_id not in seeds
    ]
    sources = recuperar_fontes_semanticas(change.query, documents, top_k=top_k)
    mapped = _artifact_map(artifact_tuple)
    candidates: list[ImpactCandidate] = []
    seen: set[str] = set()

    for source in sources:
        artifact_id = source.id.rsplit(":", 2)[0]
        if artifact_id in seen or artifact_id not in mapped:
            continue
        seen.add(artifact_id)
        confidence = min(1.0, max(0.0, float(source.score)))
        candidates.append(
            ImpactCandidate(
                artifact_id=artifact_id,
                relation="SEMANTIC_SIMILARITY",
                confidence=confidence,
                evidence=(mapped[artifact_id].source_uri, f"semantic_score={source.score:.4f}"),
                reason="Artefato recuperado pelo mecanismo semântico local já usado pelo RAG do ReqSys.",
                strategy="semantic",
            )
        )
    return StrategyResult(strategy="semantic", candidates=tuple(candidates))


def _hybrid_context(
    graph: StrategyResult,
    semantic: StrategyResult,
    mapped: dict[str, ImpactArtifact],
) -> tuple[list[dict[str, Any]], dict[str, ImpactCandidate]]:
    combined: dict[str, ImpactCandidate] = {}
    for candidate in (*graph.candidates, *semantic.candidates):
        previous = combined.get(candidate.artifact_id)
        if previous is None or candidate.confidence > previous.confidence:
            combined[candidate.artifact_id] = candidate

    context: list[dict[str, Any]] = []
    for artifact_id in sorted(combined):
        artifact = mapped[artifact_id]
        candidate = combined[artifact_id]
        context.append(
            {
                "artifact_id": artifact_id,
                "kind": artifact.kind,
                "text": artifact.text,
                "source_uri": artifact.source_uri,
                "retrieval_relation": candidate.relation,
                "retrieval_confidence": candidate.confidence,
            }
        )
    return context, combined


def build_configured_llm_generator(
    *,
    provider: str | None = None,
    model: str = "",
) -> LlmGenerate:
    router = AIProviderRouter()

    def _generate(prompt: str, correlation_id: str) -> str:
        result = router.generate_text(
            provider=provider,
            model=model,
            prompt=prompt,
            system_prompt=(
                "Você seleciona candidatos de impacto somente entre os artefatos fornecidos. "
                "Não invente IDs. Responda JSON estrito, sem markdown."
            ),
            correlation_id=correlation_id,
            context="ReqSys CHANGE impact analysis",
            input_text=prompt,
        )
        return result.text

    return _generate


def _parse_llm_candidates(
    raw: str,
    *,
    allowed_ids: set[str],
    combined: dict[str, ImpactCandidate],
    mapped: dict[str, ImpactArtifact],
) -> tuple[ImpactCandidate, ...]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ChangeImpactValidationError("LLM retornou JSON inválido") from exc
    rows = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ChangeImpactValidationError("LLM deve retornar objeto com candidates[]")

    candidates: list[ImpactCandidate] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        artifact_id = str(row.get("artifact_id") or "").strip()
        if artifact_id not in allowed_ids or artifact_id in seen:
            continue
        try:
            confidence = float(row.get("confidence"))
        except (TypeError, ValueError):
            continue
        if not 0.0 <= confidence <= 1.0:
            continue
        relation = str(row.get("relation") or "LLM_SELECTED").strip()[:120] or "LLM_SELECTED"
        reason = (
            str(
                row.get("reason")
                or "Selecionado pelo LLM a partir do contexto recuperado."
            )
            .strip()[:1000]
        )
        retrieval = combined[artifact_id]
        evidence = tuple(dict.fromkeys((*retrieval.evidence, mapped[artifact_id].source_uri)))
        candidates.append(
            ImpactCandidate(
                artifact_id=artifact_id,
                relation=relation,
                confidence=confidence,
                evidence=evidence,
                reason=reason,
                strategy="hybrid_rag_llm",
            )
        )
        seen.add(artifact_id)
    return tuple(candidates)


def hybrid_candidates(
    change: ImpactChange,
    artifacts: Iterable[ImpactArtifact],
    *,
    llm_generate: LlmGenerate | None,
    graph_depth: int = 2,
    semantic_top_k: int = 6,
    correlation_id: str | None = None,
) -> StrategyResult:
    artifact_tuple = tuple(artifacts)
    mapped = _artifact_map(artifact_tuple)
    graph = graph_candidates(change, artifact_tuple, max_depth=graph_depth)
    semantic = semantic_candidates(change, artifact_tuple, top_k=semantic_top_k)
    context, combined = _hybrid_context(graph, semantic, mapped)

    if llm_generate is None:
        fallback = tuple(
            ImpactCandidate(
                artifact_id=c.artifact_id,
                relation=c.relation,
                confidence=c.confidence,
                evidence=c.evidence,
                reason=c.reason,
                strategy="hybrid_retrieval_fallback",
            )
            for c in sorted(
                combined.values(),
                key=lambda item: (-item.confidence, item.artifact_id),
            )
        )
        return StrategyResult(
            strategy="hybrid_rag_llm",
            candidates=fallback,
            llm_status="disabled",
        )

    prompt = json.dumps(
        {
            "task": "Selecione apenas artefatos realmente impactados pela mudança.",
            "change_id": change.change_id,
            "query": change.query,
            "required_output": {
                "candidates": [
                    {
                        "artifact_id": "ID existente no contexto",
                        "relation": "tipo de relação",
                        "confidence": "0..1",
                        "reason": "justificativa curta baseada no contexto",
                    }
                ]
            },
            "context": context,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    correlation = correlation_id or f"change-impact-{change.change_id}"
    try:
        raw = llm_generate(prompt, correlation)
        selected = _parse_llm_candidates(
            raw,
            allowed_ids=set(combined),
            combined=combined,
            mapped=mapped,
        )
    except (ChangeImpactValidationError, RuntimeError, ValueError):
        return StrategyResult(
            strategy="hybrid_rag_llm",
            candidates=(),
            llm_status="invalid_or_unavailable",
        )

    return StrategyResult(
        strategy="hybrid_rag_llm",
        candidates=selected,
        llm_status="used",
    )


def evaluate_strategy(
    change: HistoricalChange,
    result: StrategyResult,
    artifacts: Iterable[ImpactArtifact],
) -> BenchmarkMetrics:
    artifact_tuple = tuple(artifacts)
    candidate_ids = {item.artifact_id for item in result.candidates}
    truth = set(change.ground_truth)
    true_positives = len(candidate_ids & truth)
    recall = true_positives / len(truth)
    precision = true_positives / len(candidate_ids) if candidate_ids else 0.0
    review_denominator = max(
        1,
        len(artifact_tuple) - len(set(change.seed_artifact_ids)),
    )
    return BenchmarkMetrics(
        strategy=result.strategy,
        retrieved=len(candidate_ids),
        true_positives=true_positives,
        recall=round(recall, 4),
        precision=round(precision, 4),
        review_rate=round(len(candidate_ids) / review_denominator, 4),
        llm_status=result.llm_status,
    )


def load_dataset(
    payload: dict[str, Any],
) -> tuple[tuple[ImpactArtifact, ...], tuple[HistoricalChange, ...]]:
    artifacts = tuple(
        ImpactArtifact(
            artifact_id=str(item["artifact_id"]),
            kind=str(item["kind"]),
            text=str(item["text"]),
            source_uri=str(item["source_uri"]),
            links=tuple(item.get("links") or ()),
        )
        for item in payload.get("artifacts") or []
    )
    changes = tuple(
        HistoricalChange(
            change_id=str(item["change_id"]),
            query=str(item["query"]),
            seed_artifact_ids=tuple(item.get("seed_artifact_ids") or ()),
            ground_truth=frozenset(item.get("ground_truth") or ()),
        )
        for item in payload.get("changes") or []
    )
    return validate_dataset(artifacts, changes)
