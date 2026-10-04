from pathlib import Path

from app.services.diagram_generator import (
    ASTAnalyzer,
    DiagramGenerationUseCase,
    DiagramType,
    FileDiagramRepository,
    MermaidGenerator,
)


SAMPLE = """
from abc import ABC

class RequirementPort(ABC):
    def save(self):
        pass

class SqlRequirementAdapter(RequirementPort):
    def save(self):
        pass

class Requirement:
    def approve(self):
        pass

def handle_requirement(value):
    return value
"""


def test_analyzer_detecta_portas_adaptadores_e_dominio(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text(SAMPLE, encoding="utf-8")

    analysis = ASTAnalyzer().analyze(source)

    assert [item["name"] for item in analysis.interfaces] == ["RequirementPort"]
    assert [item["name"] for item in analysis.adapters] == ["SqlRequirementAdapter"]
    assert "Requirement" in [item["name"] for item in analysis.domain_classes]
    assert "handle_requirement" in [item["name"] for item in analysis.functions]


def test_generator_cria_mermaid_class_e_hexagonal(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text(SAMPLE, encoding="utf-8")
    analysis = ASTAnalyzer().analyze(source)
    generator = MermaidGenerator()

    assert "classDiagram" in generator.generate_class_diagram(analysis)
    assert "graph TB" in generator.generate_hexagonal_diagram(analysis)
    assert "flowchart TD" in generator.generate_flowchart(analysis)


def test_usecase_salva_manifest_e_respeita_idempotencia(tmp_path: Path):
    source = tmp_path / "sample.py"
    source.write_text(SAMPLE, encoding="utf-8")
    repository = FileDiagramRepository(tmp_path / ".diagrams")
    usecase = DiagramGenerationUseCase(repository=repository)

    first = usecase.execute(source, [DiagramType.CLASS], correlation_id="corr-1")
    second = usecase.execute(source, [DiagramType.CLASS], correlation_id="corr-1")
    manifest = repository.list_diagrams()

    assert sum(1 for item in first.values() if item["changed"]) == 1
    assert sum(1 for item in second.values() if item["changed"]) == 0
    assert len(manifest["diagrams"]) == 1
