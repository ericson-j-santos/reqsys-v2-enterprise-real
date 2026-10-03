"""Nucleo do servidor automatico de fluxogramas, diagramas e BPMN."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET  # nosec B405 - only builds XML; never parses untrusted XML
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.services.process_artifact_repository import VersionedProcessArtifactRepository


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
    """Valida, gera BPMN/Mermaid e persiste revisoes imutaveis."""

    def __init__(self, repository: VersionedProcessArtifactRepository | None = None) -> None:
        self.repository = repository or VersionedProcessArtifactRepository()

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

        unreachable = sorted(node_id_set - self._reachable_nodes(starts[0].node_id, definition.edges))
        if unreachable:
            raise ProcessValidationError(f"nos inacessiveis: {', '.join(unreachable)}")

    def generate(self, definition: ProcessDefinition, correlation_id: str) -> dict[str, Any]:
        self.validate(definition)
        mermaid = self.to_mermaid(definition)
        bpmn_xml = self.to_bpmn_xml(definition)
        generated_at = datetime.now(UTC).isoformat()
        content_hash = hashlib.sha256(f"{mermaid}\n{bpmn_xml}".encode("utf-8")).hexdigest()
        result = {
            "schema_version": "1.1.0",
            "process_id": definition.process_id,
            "process_name": definition.name,
            "process_version": definition.version,
            "generated_at": generated_at,
            "correlation_id": correlation_id,
            "content_hash": content_hash,
            "formats": {"mermaid": mermaid, "bpmn_2_0_xml": bpmn_xml},
            "metrics": {
                "nodes": len(definition.nodes),
                "edges": len(definition.edges),
                "decisions": sum(node.node_type == NodeType.DECISION for node in definition.nodes),
            },
        }
        persisted = self.repository.save(result)
        result["persistence"] = asdict(persisted)
        return result

    def list_versions(self, process_id: str) -> list[dict[str, Any]]:
        return self.repository.list_versions(process_id)

    def to_mermaid(self, definition: ProcessDefinition) -> str:
        lines = ["flowchart TD"]
        for node in definition.nodes:
            node_id = self._safe_id(node.node_id)
            label = self._escape_mermaid(node.name)
            if node.node_type == NodeType.START:
                lines.append(f'    {node_id}(["{label}"])')
            elif node.node_type == NodeType.END:
                lines.append(f'    {node_id}(("{label}"))')
            elif node.node_type == NodeType.DECISION:
                lines.append(f'    {node_id}{{"{label}"}}')
            else:
                lines.append(f'    {node_id}["{label}"]')
        for edge in definition.edges:
            source = self._safe_id(edge.source)
            target = self._safe_id(edge.target)
            lines.append(
                f'    {source} -->|"{self._escape_mermaid(edge.label)}"| {target}'
                if edge.label
                else f"    {source} --> {target}"
            )
        return "\n".join(lines)

    def to_bpmn_xml(self, definition: ProcessDefinition) -> str:
        bpmn = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        bpmndi = "http://www.omg.org/spec/BPMN/20100524/DI"
        dc = "http://www.omg.org/spec/DD/20100524/DC"
        di = "http://www.omg.org/spec/DD/20100524/DI"
        ET.register_namespace("bpmn", bpmn)
        ET.register_namespace("bpmndi", bpmndi)
        ET.register_namespace("dc", dc)
        ET.register_namespace("di", di)

        definitions = ET.Element(
            f"{{{bpmn}}}definitions",
            {
                "id": f"Definitions_{self._safe_id(definition.process_id)}",
                "targetNamespace": "https://reqsys.local/bpmn",
                "exporter": "ReqSys Automatic Diagram Server",
                "exporterVersion": "1.1.0",
            },
        )
        process_id = self._safe_id(definition.process_id)
        process = ET.SubElement(
            definitions,
            f"{{{bpmn}}}process",
            {"id": process_id, "name": definition.name, "isExecutable": "false"},
        )
        incoming_by_node = {node.node_id: [] for node in definition.nodes}
        outgoing_by_node = {node.node_id: [] for node in definition.nodes}
        for index, edge in enumerate(definition.edges, start=1):
            flow_id = f"Flow_{index}"
            outgoing_by_node[edge.source].append(flow_id)
            incoming_by_node[edge.target].append(flow_id)

        element_by_node: dict[str, ET.Element] = {}
        for node in definition.nodes:
            attrs = {"id": self._safe_id(node.node_id), "name": node.name}
            tag = {
                NodeType.START: "startEvent",
                NodeType.END: "endEvent",
                NodeType.DECISION: "exclusiveGateway",
                NodeType.TASK: "task",
            }[node.node_type]
            element_by_node[node.node_id] = ET.SubElement(process, f"{{{bpmn}}}{tag}", attrs)

        for node in definition.nodes:
            element = element_by_node[node.node_id]
            for flow_id in incoming_by_node[node.node_id]:
                ET.SubElement(element, f"{{{bpmn}}}incoming").text = flow_id
            for flow_id in outgoing_by_node[node.node_id]:
                ET.SubElement(element, f"{{{bpmn}}}outgoing").text = flow_id

        for index, edge in enumerate(definition.edges, start=1):
            attrs = {
                "id": f"Flow_{index}",
                "sourceRef": self._safe_id(edge.source),
                "targetRef": self._safe_id(edge.target),
            }
            if edge.label:
                attrs["name"] = edge.label
            ET.SubElement(process, f"{{{bpmn}}}sequenceFlow", attrs)

        positions = self._layout(definition)
        diagram = ET.SubElement(definitions, f"{{{bpmndi}}}BPMNDiagram", {"id": f"Diagram_{process_id}"})
        plane = ET.SubElement(
            diagram,
            f"{{{bpmndi}}}BPMNPlane",
            {"id": f"Plane_{process_id}", "bpmnElement": process_id},
        )
        for node in definition.nodes:
            node_id = self._safe_id(node.node_id)
            x, y, width, height = positions[node.node_id]
            shape = ET.SubElement(
                plane,
                f"{{{bpmndi}}}BPMNShape",
                {"id": f"Shape_{node_id}", "bpmnElement": node_id},
            )
            ET.SubElement(
                shape,
                f"{{{dc}}}Bounds",
                {"x": str(x), "y": str(y), "width": str(width), "height": str(height)},
            )
        for index, edge in enumerate(definition.edges, start=1):
            source = positions[edge.source]
            target = positions[edge.target]
            edge_element = ET.SubElement(
                plane,
                f"{{{bpmndi}}}BPMNEdge",
                {"id": f"Edge_Flow_{index}", "bpmnElement": f"Flow_{index}"},
            )
            ET.SubElement(
                edge_element,
                f"{{{di}}}waypoint",
                {"x": str(source[0] + source[2]), "y": str(source[1] + source[3] // 2)},
            )
            ET.SubElement(
                edge_element,
                f"{{{di}}}waypoint",
                {"x": str(target[0]), "y": str(target[1] + target[3] // 2)},
            )

        ET.indent(definitions, space="  ")
        return ET.tostring(definitions, encoding="utf-8", xml_declaration=True).decode("utf-8")

    @staticmethod
    def _layout(definition: ProcessDefinition) -> dict[str, tuple[int, int, int, int]]:
        positions: dict[str, tuple[int, int, int, int]] = {}
        for index, node in enumerate(definition.nodes):
            width, height = (36, 36) if node.node_type in {NodeType.START, NodeType.END} else (100, 80)
            if node.node_type == NodeType.DECISION:
                width, height = 50, 50
            custom_x = node.metadata.get("x")
            custom_y = node.metadata.get("y")
            x = int(custom_x) if isinstance(custom_x, int | float) else 120 + index * 180
            y = int(custom_y) if isinstance(custom_y, int | float) else 160
            positions[node.node_id] = (x, y, width, height)
        return positions

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
        return f"N_{sanitized}" if sanitized[0].isdigit() else sanitized

    @staticmethod
    def _escape_mermaid(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', "&quot;").replace("\n", " ").strip()
