"""Nucleo do servidor automatico de fluxogramas, diagramas e BPMN.

O modulo nao depende do framework web. Recebe uma definicao de processo
estruturada, valida o grafo e gera representacoes Mermaid e BPMN 2.0 XML.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET  # nosec B405 - only builds XML; never parses untrusted XML
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    START = "start"
    TASK = "task"
    DECISION = "decision"
    END = "end"


@dataclass(frozen=True)
class ProcessNode:
    node_id: str
    name: str
    node_type: NodeType
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessEdge:
    source: str
    target: str
    label: str | None = None


@dataclass(frozen=True)
class ProcessDefinition:
    process_id: str
    name: str
    nodes: list[ProcessNode]
    edges: list[ProcessEdge]
    version: str = "1.0.0"


class ProcessValidationError(ValueError):
    """Erro de contrato na definicao de processo."""


class AutomaticDiagramServer:
    """Valida processos e gera artefatos Mermaid e BPMN 2.0."""

    def validate(self, definition: ProcessDefinition) -> None:
        if not definition.process_id.strip():
            raise ProcessValidationError("process_id e obrigatorio")
        if not definition.name.strip():
            raise ProcessValidationError("name e obrigatorio")
        if not definition.nodes:
            raise ProcessValidationError("o processo deve possuir ao menos um no")

        node_ids = [node.node_id for node in definition.nodes]
        if any(not node_id.strip() for node_id in node_ids):
            raise ProcessValidationError("todos os nos devem possuir node_id")
        if len(node_ids) != len(set(node_ids)):
            raise ProcessValidationError("node_id duplicado")

        node_id_set = set(node_ids)
        for edge in definition.edges:
            if edge.source not in node_id_set:
                raise ProcessValidationError(f"origem inexistente: {edge.source}")
            if edge.target not in node_id_set:
                raise ProcessValidationError(f"destino inexistente: {edge.target}")
            if edge.source == edge.target:
                raise ProcessValidationError(f"auto referencia nao permitida: {edge.source}")

        starts = [node for node in definition.nodes if node.node_type == NodeType.START]
        ends = [node for node in definition.nodes if node.node_type == NodeType.END]
        if len(starts) != 1:
            raise ProcessValidationError("o processo deve possuir exatamente um evento inicial")
        if not ends:
            raise ProcessValidationError("o processo deve possuir ao menos um evento final")

        incoming = {node_id: 0 for node_id in node_ids}
        outgoing = {node_id: 0 for node_id in node_ids}
        for edge in definition.edges:
            incoming[edge.target] += 1
            outgoing[edge.source] += 1

        if incoming[starts[0].node_id] != 0:
            raise ProcessValidationError("o evento inicial nao pode possuir fluxo de entrada")
        for end in ends:
            if outgoing[end.node_id] != 0:
                raise ProcessValidationError(f"evento final nao pode possuir saida: {end.node_id}")

        reachable = self._reachable_nodes(starts[0].node_id, definition.edges)
        unreachable = sorted(node_id_set - reachable)
        if unreachable:
            raise ProcessValidationError(f"nos inacessiveis: {', '.join(unreachable)}")

    def generate(self, definition: ProcessDefinition, correlation_id: str) -> dict[str, Any]:
        self.validate(definition)
        mermaid = self.to_mermaid(definition)
        bpmn_xml = self.to_bpmn_xml(definition)
        generated_at = datetime.now(UTC).isoformat()
        content_hash = hashlib.sha256(f"{mermaid}\n{bpmn_xml}".encode("utf-8")).hexdigest()
        return {
            "schema_version": "1.0.0",
            "process_id": definition.process_id,
            "process_name": definition.name,
            "process_version": definition.version,
            "generated_at": generated_at,
            "correlation_id": correlation_id,
            "content_hash": content_hash,
            "formats": {
                "mermaid": mermaid,
                "bpmn_2_0_xml": bpmn_xml,
            },
            "metrics": {
                "nodes": len(definition.nodes),
                "edges": len(definition.edges),
                "decisions": sum(node.node_type == NodeType.DECISION for node in definition.nodes),
            },
        }

    def to_mermaid(self, definition: ProcessDefinition) -> str:
        lines = ["flowchart TD"]
        for node in definition.nodes:
            node_id = self._safe_id(node.node_id)
            label = self._escape_mermaid(node.name)
            if node.node_type == NodeType.START:
                lines.append(f"    {node_id}([\"{label}\"])")
            elif node.node_type == NodeType.END:
                lines.append(f"    {node_id}((\"{label}\"))")
            elif node.node_type == NodeType.DECISION:
                lines.append(f"    {node_id}{{\"{label}\"}}")
            else:
                lines.append(f"    {node_id}[\"{label}\"]")

        for edge in definition.edges:
            source = self._safe_id(edge.source)
            target = self._safe_id(edge.target)
            if edge.label:
                lines.append(f"    {source} -->|\"{self._escape_mermaid(edge.label)}\"| {target}")
            else:
                lines.append(f"    {source} --> {target}")
        return "\n".join(lines)

    def to_bpmn_xml(self, definition: ProcessDefinition) -> str:
        ET.register_namespace("bpmn", "http://www.omg.org/spec/BPMN/20100524/MODEL")
        namespace = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        definitions = ET.Element(
            f"{{{namespace}}}definitions",
            {
                "id": f"Definitions_{self._safe_id(definition.process_id)}",
                "targetNamespace": "https://reqsys.local/bpmn",
                "exporter": "ReqSys Automatic Diagram Server",
                "exporterVersion": "1.0.0",
            },
        )
        process = ET.SubElement(
            definitions,
            f"{{{namespace}}}process",
            {
                "id": self._safe_id(definition.process_id),
                "name": definition.name,
                "isExecutable": "false",
            },
        )

        incoming_by_node: dict[str, list[str]] = {node.node_id: [] for node in definition.nodes}
        outgoing_by_node: dict[str, list[str]] = {node.node_id: [] for node in definition.nodes}
        for index, edge in enumerate(definition.edges, start=1):
            flow_id = f"Flow_{index}"
            outgoing_by_node[edge.source].append(flow_id)
            incoming_by_node[edge.target].append(flow_id)

        element_by_node: dict[str, ET.Element] = {}
        for node in definition.nodes:
            attrs = {"id": self._safe_id(node.node_id), "name": node.name}
            if node.node_type == NodeType.START:
                element = ET.SubElement(process, f"{{{namespace}}}startEvent", attrs)
            elif node.node_type == NodeType.END:
                element = ET.SubElement(process, f"{{{namespace}}}endEvent", attrs)
            elif node.node_type == NodeType.DECISION:
                element = ET.SubElement(process, f"{{{namespace}}}exclusiveGateway", attrs)
            else:
                element = ET.SubElement(process, f"{{{namespace}}}task", attrs)
            element_by_node[node.node_id] = element

        for node in definition.nodes:
            element = element_by_node[node.node_id]
            for flow_id in incoming_by_node[node.node_id]:
                ET.SubElement(element, f"{{{namespace}}}incoming").text = flow_id
            for flow_id in outgoing_by_node[node.node_id]:
                ET.SubElement(element, f"{{{namespace}}}outgoing").text = flow_id

        for index, edge in enumerate(definition.edges, start=1):
            attrs = {
                "id": f"Flow_{index}",
                "sourceRef": self._safe_id(edge.source),
                "targetRef": self._safe_id(edge.target),
            }
            if edge.label:
                attrs["name"] = edge.label
            ET.SubElement(process, f"{{{namespace}}}sequenceFlow", attrs)

        ET.indent(definitions, space="  ")
        return ET.tostring(definitions, encoding="utf-8", xml_declaration=True).decode("utf-8")

    @staticmethod
    def _reachable_nodes(start_id: str, edges: list[ProcessEdge]) -> set[str]:
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source, []).append(edge.target)
        visited: set[str] = set()
        stack = [start_id]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            stack.extend(adjacency.get(current, []))
        return visited

    @staticmethod
    def _safe_id(value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9_]", "_", value.strip())
        if not sanitized:
            return "Node"
        if sanitized[0].isdigit():
            sanitized = f"N_{sanitized}"
        return sanitized

    @staticmethod
    def _escape_mermaid(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', "&quot;").replace("\n", " ").strip()
