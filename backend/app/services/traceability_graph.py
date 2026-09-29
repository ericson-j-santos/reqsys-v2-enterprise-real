from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.change_evidence import ChangeEvidenceRecord
from app.models.agile_runtime import AgileWorkItem
from app.models.requisito import Requisito
from app.models.vinculo_git import VinculoGit

_SATISFACTORY_EVIDENCE_STATUSES = {"PASSED", "ROLLED_BACK"}

_GIT_LINK_KIND_RELATION = {
    "pr": ("PULL_REQUEST", "implemented_by"),
    "merge_request": ("PULL_REQUEST", "implemented_by"),
    "commit": ("COMMIT", "implemented_at"),
    "branch": ("BRANCH", "developed_on"),
    "issue": ("ISSUE", "tracked_by"),
    "tag": ("RELEASE", "released_as"),
    "deploy": ("DEPLOYMENT", "deployed_as"),
}


class TraceabilityGraphService:
    """Projeta rastreabilidade existente sem criar uma nova fonte de verdade."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def build_for_requirement(self, requisito_id: int) -> dict[str, Any] | None:
        requisito = self._db.get(Requisito, requisito_id)
        if requisito is None:
            return None

        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[tuple[str, str, str], dict[str, Any]] = {}
        rejected_evidence: list[dict[str, Any]] = []
        valid_evidence_count = 0

        requirement_node = f"requirement:{requisito.codigo}"
        self._add_node(
            nodes,
            node_id=requirement_node,
            kind="REQUIREMENT",
            label=requisito.codigo,
            source_uri=f"/v1/requisitos/{requisito.id}",
            metadata={
                "requisito_id": requisito.id,
                "titulo": requisito.titulo,
                "status": requisito.status,
            },
        )

        work_items = (
            self._db.query(AgileWorkItem)
            .filter(AgileWorkItem.requisito_id == requisito.id)
            .order_by(AgileWorkItem.codigo, AgileWorkItem.id)
            .all()
        )
        for item in work_items:
            node_id = f"work_item:{item.id}"
            self._add_node(
                nodes,
                node_id=node_id,
                kind="WORK_ITEM",
                label=item.codigo,
                source_uri=item.change_url,
                metadata={
                    "tipo": item.tipo,
                    "status": item.status,
                    "repositorio": item.repositorio,
                    "branch": item.branch,
                    "change_provider": item.change_provider,
                    "change_id": item.change_id,
                    "ci_provider": item.ci_provider,
                    "ci_run_id": item.ci_run_id,
                    "ci_status": item.ci_status,
                    "deploy_status": item.deploy_status,
                    "ambiente_deploy": item.ambiente_deploy,
                },
            )
            self._add_edge(
                edges,
                source=requirement_node,
                target=node_id,
                relation="planned_as",
                evidence_status="reference",
            )

        links = (
            self._db.query(VinculoGit)
            .filter(VinculoGit.requisito_id == requisito.id)
            .order_by(
                VinculoGit.provedor,
                VinculoGit.repo,
                VinculoGit.tipo,
                VinculoGit.referencia,
                VinculoGit.id,
            )
            .all()
        )
        for link in links:
            kind, relation = _GIT_LINK_KIND_RELATION.get(
                link.tipo,
                ("EXTERNAL_REFERENCE", "related_to"),
            )
            node_id = (
                f"git:{link.provedor}:{link.repo}:{link.tipo}:{link.referencia}"
            )
            self._add_node(
                nodes,
                node_id=node_id,
                kind=kind,
                label=link.referencia,
                source_uri=link.url,
                metadata={
                    "provider": link.provedor,
                    "repository": link.repo,
                    "type": link.tipo,
                    "environment": link.ambiente,
                    "title": link.titulo,
                },
            )
            self._add_edge(
                edges,
                source=requirement_node,
                target=node_id,
                relation=relation,
                evidence_status="reference",
            )

        evidence_rows = (
            self._db.query(ChangeEvidenceRecord)
            .filter(ChangeEvidenceRecord.requirement_ref == requisito.codigo)
            .order_by(
                ChangeEvidenceRecord.observed_at,
                ChangeEvidenceRecord.event_id,
            )
            .all()
        )
        for record in evidence_rows:
            reasons = self._evidence_rejection_reasons(record)
            evidence_status = "verified" if not reasons else "rejected"
            if reasons:
                rejected_evidence.append(
                    {
                        "event_id": record.event_id,
                        "head_sha": record.head_sha,
                        "runtime_sha": record.runtime_sha,
                        "reasons": reasons,
                    }
                )
            else:
                valid_evidence_count += 1

            sdd_node = f"sdd:{record.sdd_ref}"
            pr_node = f"pull_request:{record.pull_request_ref}"
            commit_node = f"commit:{record.head_sha.lower()}"
            ci_node = f"ci_run:{record.ci_run_id}"
            deployment_node = f"deployment:{record.deployment_ref}"
            runtime_node = f"runtime_evidence:{record.event_id}"

            self._add_node(
                nodes,
                node_id=sdd_node,
                kind="SDD",
                label=record.sdd_ref,
                source_uri=record.sdd_ref,
                metadata={},
            )
            self._add_node(
                nodes,
                node_id=pr_node,
                kind="PULL_REQUEST",
                label=record.pull_request_ref,
                source_uri=record.pull_request_ref,
                metadata={},
            )
            self._add_node(
                nodes,
                node_id=commit_node,
                kind="COMMIT",
                label=record.head_sha.lower(),
                source_uri=None,
                metadata={"head_sha": record.head_sha.lower()},
            )
            self._add_node(
                nodes,
                node_id=ci_node,
                kind="CI_RUN",
                label=record.ci_run_id,
                source_uri=None,
                metadata={
                    "conclusion": record.ci_conclusion,
                    "head_sha": record.head_sha.lower(),
                },
            )
            self._add_node(
                nodes,
                node_id=deployment_node,
                kind="DEPLOYMENT",
                label=record.deployment_ref,
                source_uri=None,
                metadata={"environment": record.environment},
            )
            self._add_node(
                nodes,
                node_id=runtime_node,
                kind="RUNTIME_EVIDENCE",
                label=record.event_id,
                source_uri=record.post_deploy_evidence_uri,
                metadata={
                    "status": record.status,
                    "head_sha": record.head_sha.lower(),
                    "runtime_sha": record.runtime_sha.lower(),
                    "environment": record.environment,
                    "sha256": record.post_deploy_evidence_sha256,
                    "observed_at": record.observed_at.isoformat(),
                    "correlation_id": record.correlation_id,
                    "rejection_reasons": reasons,
                },
            )

            self._add_edge(
                edges,
                source=requirement_node,
                target=sdd_node,
                relation="specified_by",
                evidence_status="reference",
            )
            self._add_edge(
                edges,
                source=requirement_node,
                target=pr_node,
                relation="implemented_by",
                evidence_status="reference",
            )
            self._add_edge(
                edges,
                source=pr_node,
                target=commit_node,
                relation="resolved_to",
                evidence_status="reference",
            )
            self._add_edge(
                edges,
                source=commit_node,
                target=ci_node,
                relation="verified_by",
                evidence_status=evidence_status,
                reasons=reasons,
            )
            self._add_edge(
                edges,
                source=commit_node,
                target=deployment_node,
                relation="deployed_as",
                evidence_status=evidence_status,
                reasons=reasons,
            )
            self._add_edge(
                edges,
                source=deployment_node,
                target=runtime_node,
                relation="observed_as",
                evidence_status=evidence_status,
                reasons=reasons,
            )

        ordered_nodes = sorted(nodes.values(), key=lambda item: item["id"])
        ordered_edges = sorted(
            edges.values(),
            key=lambda item: (item["source"], item["relation"], item["target"]),
        )
        rejected_evidence.sort(key=lambda item: item["event_id"])

        return {
            "schema_version": "1.0.0",
            "requirement": {
                "id": requisito.id,
                "code": requisito.codigo,
                "status": requisito.status,
            },
            "nodes": ordered_nodes,
            "edges": ordered_edges,
            "rejected_evidence": rejected_evidence,
            "summary": {
                "node_count": len(ordered_nodes),
                "edge_count": len(ordered_edges),
                "valid_evidence_count": valid_evidence_count,
                "rejected_evidence_count": len(rejected_evidence),
            },
        }

    @staticmethod
    def _evidence_rejection_reasons(record: ChangeEvidenceRecord) -> list[str]:
        reasons: list[str] = []
        if record.ci_conclusion.lower() != "success":
            reasons.append("ci_not_success")
        if record.runtime_sha.lower() != record.head_sha.lower():
            reasons.append("runtime_sha_mismatch")
        if record.status.upper() not in _SATISFACTORY_EVIDENCE_STATUSES:
            reasons.append("runtime_status_not_satisfactory")
        return reasons

    @staticmethod
    def _add_node(
        nodes: dict[str, dict[str, Any]],
        *,
        node_id: str,
        kind: str,
        label: str,
        source_uri: str | None,
        metadata: dict[str, Any],
    ) -> None:
        candidate = {
            "id": node_id,
            "kind": kind,
            "label": label,
            "source_uri": source_uri,
            "metadata": metadata,
        }
        existing = nodes.get(node_id)
        if existing is None:
            nodes[node_id] = candidate
            return
        if existing != candidate:
            merged_metadata = dict(existing.get("metadata") or {})
            merged_metadata.update(metadata)
            existing["metadata"] = merged_metadata
            if not existing.get("source_uri") and source_uri:
                existing["source_uri"] = source_uri

    @staticmethod
    def _add_edge(
        edges: dict[tuple[str, str, str], dict[str, Any]],
        *,
        source: str,
        target: str,
        relation: str,
        evidence_status: str,
        reasons: list[str] | None = None,
    ) -> None:
        key = (source, relation, target)
        candidate = {
            "source": source,
            "target": target,
            "relation": relation,
            "evidence_status": evidence_status,
            "reasons": list(reasons or []),
        }
        existing = edges.get(key)
        if existing is None:
            edges[key] = candidate
            return
        if existing["evidence_status"] == "rejected":
            return
        if evidence_status == "rejected":
            edges[key] = candidate
