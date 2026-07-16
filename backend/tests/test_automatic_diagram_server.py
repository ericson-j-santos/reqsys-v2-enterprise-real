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


def _valid_process() -> ProcessDefinition:
    return ProcessDefinition(
        process_id="approval_flow",
        name="Aprovacao de requisito",
        nodes=[
            ProcessNode("start", "Demanda recebida", NodeType.START),
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


def test_generate_returns_mermaid_bpmn_hash_and_metrics():
    result = AutomaticDiagramServer().generate(_valid_process(), correlation_id="test-123")

    assert result["correlation_id"] == "test-123"
    assert result["metrics"] == {"nodes": 6, "edges": 6, "decisions": 1}
    assert len(result["content_hash"]) == 64
    assert "flowchart TD" in result["formats"]["mermaid"]
    assert "exclusiveGateway" in result["formats"]["bpmn_2_0_xml"]


def test_bpmn_output_is_valid_xml_and_contains_sequence_flows():
    xml_content = AutomaticDiagramServer().to_bpmn_xml(_valid_process())
    root = ET.fromstring(xml_content)
    namespace = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}

    assert root.tag.endswith("definitions")
    assert len(root.findall(".//bpmn:sequenceFlow", namespace)) == 6
    assert len(root.findall(".//bpmn:startEvent", namespace)) == 1
    assert len(root.findall(".//bpmn:endEvent", namespace)) == 1


def test_validation_rejects_unreachable_node():
    process = _valid_process()
    invalid = ProcessDefinition(
        process_id=process.process_id,
        name=process.name,
        nodes=[*process.nodes, ProcessNode("orphan", "No isolado", NodeType.TASK)],
        edges=process.edges,
    )

    with pytest.raises(ProcessValidationError, match="nos inacessiveis: orphan"):
        AutomaticDiagramServer().validate(invalid)


def test_validation_rejects_duplicate_node_id():
    process = _valid_process()
    invalid = ProcessDefinition(
        process_id=process.process_id,
        name=process.name,
        nodes=[*process.nodes, ProcessNode("start", "Duplicado", NodeType.TASK)],
        edges=process.edges,
    )

    with pytest.raises(ProcessValidationError, match="node_id duplicado"):
        AutomaticDiagramServer().validate(invalid)
