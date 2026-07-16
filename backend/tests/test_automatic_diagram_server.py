import json
import xml.etree.ElementTree as ET

import pytest

from app.services.automatic_diagram_server import (
    AutomaticDiagramServer,
    NodeType,
    ProcessDefinition,
    ProcessEdge,
    ProcessNode,
    ProcessValidationError,
)
from app.services.process_artifact_repository import VersionedProcessArtifactRepository


def _valid_process() -> ProcessDefinition:
    return ProcessDefinition(
        process_id="approval_flow",
        name="Aprovacao de requisito",
        nodes=[
            ProcessNode("start", "Demanda recebida", NodeType.START, {"x": 80, "y": 140}),
            ProcessNode("analyze", "Analisar requisito", NodeType.TASK),
            ProcessNode("approved", "Requisito aprovado?", NodeType.DECISION),
            ProcessNode("publish", "Publicar backlog", NodeType.TASK),
            ProcessNode("reject", "Solicitar ajustes", NodeType.TASK),
            ProcessNode("end", "Processo finalizado", NodeType.END),
        ],
        edges=[
            ProcessEdge("start", "analyze"),
            ProcessEdge("analyze", "approved"),
            ProcessEdge("approved", "publish", "sim"),
            ProcessEdge("approved", "reject", "nao"),
            ProcessEdge("publish", "end"),
            ProcessEdge("reject", "end"),
        ],
    )


def test_generate_returns_mermaid_bpmn_hash_metrics_and_persistence(tmp_path):
    repository = VersionedProcessArtifactRepository(tmp_path)
    result = AutomaticDiagramServer(repository).generate(_valid_process(), correlation_id="test-123")

    assert result["correlation_id"] == "test-123"
    assert result["metrics"] == {"nodes": 6, "edges": 6, "decisions": 1}
    assert len(result["content_hash"]) == 64
    assert "flowchart TD" in result["formats"]["mermaid"]
    assert "exclusiveGateway" in result["formats"]["bpmn_2_0_xml"]
    assert (tmp_path / "approval_flow").exists()
    assert result["persistence"]["bpmn_file"].endswith("process.bpmn")

    manifest = json.loads((tmp_path / "approval_flow" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["latest_revision"].startswith("1.0.0-")
    assert len(manifest["versions"]) == 1


def test_bpmn_output_contains_di_shapes_edges_and_sequence_flows(tmp_path):
    server = AutomaticDiagramServer(VersionedProcessArtifactRepository(tmp_path))
    xml_content = server.to_bpmn_xml(_valid_process())
    root = ET.fromstring(xml_content)
    namespace = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        "dc": "http://www.omg.org/spec/DD/20100524/DC",
        "di": "http://www.omg.org/spec/DD/20100524/DI",
    }

    assert root.tag.endswith("definitions")
    assert len(root.findall(".//bpmn:sequenceFlow", namespace)) == 6
    assert len(root.findall(".//bpmndi:BPMNShape", namespace)) == 6
    assert len(root.findall(".//bpmndi:BPMNEdge", namespace)) == 6
    assert len(root.findall(".//dc:Bounds", namespace)) == 6
    assert len(root.findall(".//di:waypoint", namespace)) == 12


def test_same_version_and_content_is_idempotent_in_manifest(tmp_path):
    server = AutomaticDiagramServer(VersionedProcessArtifactRepository(tmp_path))
    first = server.generate(_valid_process(), correlation_id="first")
    second = server.generate(_valid_process(), correlation_id="second")

    assert first["content_hash"] == second["content_hash"]
    versions = server.list_versions("approval_flow")
    assert len(versions) == 1
    assert versions[0]["correlation_id"] == "second"


def test_validation_rejects_unreachable_node(tmp_path):
    process = _valid_process()
    invalid = ProcessDefinition(
        process_id=process.process_id,
        name=process.name,
        nodes=[*process.nodes, ProcessNode("orphan", "No isolado", NodeType.TASK)],
        edges=process.edges,
    )

    with pytest.raises(ProcessValidationError, match="nos inacessiveis: orphan"):
        AutomaticDiagramServer(VersionedProcessArtifactRepository(tmp_path)).validate(invalid)


def test_validation_rejects_duplicate_node_id(tmp_path):
    process = _valid_process()
    invalid = ProcessDefinition(
        process_id=process.process_id,
        name=process.name,
        nodes=[*process.nodes, ProcessNode("start", "Duplicado", NodeType.TASK)],
        edges=process.edges,
    )

    with pytest.raises(ProcessValidationError, match="node_id duplicado"):
        AutomaticDiagramServer(VersionedProcessArtifactRepository(tmp_path)).validate(invalid)
