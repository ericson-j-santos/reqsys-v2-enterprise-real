from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from app.core.envelope import ok
from app.services.automatic_diagram_server import (
    AutomaticDiagramServer,
    NodeType,
    ProcessDefinition,
    ProcessEdge,
    ProcessNode,
    ProcessValidationError,
)
from app.services.diagram_generator import (
    ASTAnalyzer,
    DiagramGenerationUseCase,
    FileDiagramRepository,
    MermaidGenerator,
    diagram_types_from_option,
)
from app.services.process_artifact_repository import (
    ProcessArtifactComparisonError,
    ProcessArtifactNotFoundError,
    VersionedProcessArtifactRepository,
)

router = APIRouter(prefix="/v1/diagramas", tags=["Arquitetura Viva"])

_repository = FileDiagramRepository()
_artifact_repository = VersionedProcessArtifactRepository()
_analyzer = ASTAnalyzer()
_generator = MermaidGenerator()
_usecase = DiagramGenerationUseCase(_analyzer, _generator, _repository)
_automatic_server = AutomaticDiagramServer(repository=_artifact_repository)


class CodeAnalysisRequest(BaseModel):
    filename: str
    content: str


class ProcessNodeRequest(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    type: NodeType
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessEdgeRequest(BaseModel):
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=240)


class AutomaticProcessRequest(BaseModel):
    process_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    version: str = Field(default="1.0.0", min_length=1, max_length=40)
    nodes: list[ProcessNodeRequest] = Field(min_length=1, max_length=500)
    edges: list[ProcessEdgeRequest] = Field(default_factory=list, max_length=1000)

    def to_domain(self) -> ProcessDefinition:
        return ProcessDefinition(
            process_id=self.process_id,
            name=self.name,
            version=self.version,
            nodes=[
                ProcessNode(
                    node_id=node.id,
                    name=node.name,
                    node_type=node.type,
                    metadata=node.metadata,
                )
                for node in self.nodes
            ],
            edges=[
                ProcessEdge(source=edge.source, target=edge.target, label=edge.label)
                for edge in self.edges
            ],
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "name": self.name,
            "version": self.version,
            "nodes": [
                {"id": node.id, "name": node.name, "type": node.type.value, "metadata": node.metadata}
                for node in self.nodes
            ],
            "edges": [
                {"source": edge.source, "target": edge.target, "label": edge.label}
                for edge in self.edges
            ],
        }


@router.post("/analisar")
def analisar_codigo(payload: CodeAnalysisRequest):
    if not payload.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Envie um arquivo Python .py")

    with NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as tmp:
        tmp.write(payload.content)
        tmp_path = Path(tmp.name)

    try:
        analysis = _analyzer.analyze(tmp_path)
        return ok(
            {
                "filename": payload.filename,
                "functions": analysis.functions,
                "classes": analysis.classes,
                "interfaces": analysis.interfaces,
                "adapters": analysis.adapters,
                "domain_classes": analysis.domain_classes,
                "class_diagram": _generator.generate_class_diagram(analysis),
                "flowchart": _generator.generate_flowchart(analysis),
                "hexagonal": _generator.generate_hexagonal_diagram(analysis),
            }
        )
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/gerar")
def gerar_diagramas(filepath: str, types: str = "all", correlation_id: str = "api-local"):
    path = Path(filepath)
    if not path.exists() or path.suffix != ".py":
        raise HTTPException(status_code=400, detail="Arquivo Python nao encontrado")
    try:
        diagram_types = diagram_types_from_option(types)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tipo de diagrama invalido") from exc
    return ok(_usecase.execute(path, diagram_types, correlation_id=correlation_id))


@router.post("/automatico/gerar")
def gerar_processo_automatico(
    payload: AutomaticProcessRequest,
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
):
    correlation_id = (x_correlation_id or "diagram-api-local").strip()[:160]
    try:
        result = _automatic_server.generate(payload.to_domain(), correlation_id=correlation_id)
        result["definition"] = payload.snapshot()
        persisted = _artifact_repository.save(result)
        result["persistence"] = {
            "process_id": persisted.process_id,
            "version": persisted.version,
            "revision": persisted.revision,
            "content_hash": persisted.content_hash,
            "generated_at": persisted.generated_at,
            "directory": persisted.directory,
            "mermaid_file": persisted.mermaid_file,
            "bpmn_file": persisted.bpmn_file,
            "metadata_file": persisted.metadata_file,
        }
    except ProcessValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(result)


@router.post("/automatico/mermaid", response_class=Response)
def gerar_mermaid(payload: AutomaticProcessRequest):
    try:
        definition = payload.to_domain()
        _automatic_server.validate(definition)
        content = _automatic_server.to_mermaid(definition)
    except ProcessValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(content=content, media_type="text/plain; charset=utf-8")


@router.post("/automatico/bpmn", response_class=Response)
def gerar_bpmn(payload: AutomaticProcessRequest):
    try:
        definition = payload.to_domain()
        _automatic_server.validate(definition)
        content = _automatic_server.to_bpmn_xml(definition)
    except ProcessValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/xml",
        headers={"Content-Disposition": f'inline; filename="{payload.process_id}.bpmn"'},
    )


@router.get("/automatico/processos/{process_id}/versoes")
def listar_versoes(process_id: str):
    versions = _artifact_repository.list_versions(process_id)
    return ok({"process_id": process_id, "total": len(versions), "versions": versions})


@router.get("/automatico/processos/{process_id}/versoes/{revision}")
def obter_versao(process_id: str, revision: str, include_formats: bool = Query(default=True)):
    try:
        artifact = _artifact_repository.get_version(process_id, revision)
    except ProcessArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not include_formats:
        artifact.pop("formats", None)
    return ok(artifact)


@router.get("/automatico/processos/{process_id}/comparar")
def comparar_versoes(
    process_id: str,
    base_revision: str = Query(min_length=1, max_length=200),
    target_revision: str = Query(min_length=1, max_length=200),
):
    if base_revision == target_revision:
        raise HTTPException(status_code=400, detail="base_revision e target_revision devem ser diferentes")
    try:
        comparison = _artifact_repository.compare_versions(process_id, base_revision, target_revision)
    except ProcessArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProcessArtifactComparisonError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ok(comparison)


@router.get("/automatico/contrato")
def contrato_automatico():
    return ok(
        {
            "schema_version": "1.2.0",
            "service": "reqsys-automatic-diagram-server",
            "supported_formats": ["mermaid", "bpmn_2_0_xml"],
            "supported_node_types": [item.value for item in NodeType],
            "limits": {"nodes": 500, "edges": 1000},
            "endpoints": [
                {"method": "POST", "path": "/v1/diagramas/automatico/gerar"},
                {"method": "POST", "path": "/v1/diagramas/automatico/mermaid"},
                {"method": "POST", "path": "/v1/diagramas/automatico/bpmn"},
                {"method": "GET", "path": "/v1/diagramas/automatico/processos/{process_id}/versoes"},
                {"method": "GET", "path": "/v1/diagramas/automatico/processos/{process_id}/versoes/{revision}"},
                {"method": "GET", "path": "/v1/diagramas/automatico/processos/{process_id}/comparar"},
            ],
        }
    )


@router.get("/stats")
def stats():
    manifest = _repository.list_diagrams()
    by_type: dict[str, int] = {}
    for item in manifest.get("diagrams", {}).values():
        dtype = item.get("diagram_type", "unknown")
        by_type[dtype] = by_type.get(dtype, 0) + 1
    return ok(
        {
            "total": len(manifest.get("diagrams", {})),
            "by_type": by_type,
            "last_updated": manifest.get("last_updated"),
            "diagrams": manifest.get("diagrams", {}),
            "automatic_server": {
                "status": "available",
                "formats": ["mermaid", "bpmn_2_0_xml"],
                "version_history": True,
                "structural_diff": True,
            },
        }
    )


@router.get("/health")
def health():
    return ok(
        {
            "status": "healthy",
            "service": "diagram-generator",
            "version": "1.2.0",
            "capabilities": [
                "python_ast",
                "mermaid",
                "bpmn_2_0_xml",
                "version_history",
                "structural_diff",
            ],
        }
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(
        """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ReqSys Diagramas</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #f8fafc; color: #0f172a; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 20px; }
    button { background: #166534; color: #fff; border: 0; border-radius: 6px; padding: 10px 14px; cursor: pointer; }
    input { padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 18px; }
    .card { border: 1px solid #cbd5e1; border-radius: 8px; background: #fff; padding: 16px; }
    .stat { font-size: 28px; font-weight: 700; margin-top: 6px; }
    .mermaid { overflow: auto; background: #fff; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; margin: 12px 0; }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>ReqSys Arquitetura Viva</h1>
      <p>Diagramas, BPMN 2.0, histórico de versões e comparação estrutural.</p>
    </div>
    <a href="/v1/diagramas/automatico/contrato">Contrato JSON</a>
  </header>
  <section class="grid" id="stats"></section>
  <section class="card">
    <h2>Analisar arquivo Python</h2>
    <input type="file" id="fileInput" accept=".py">
    <button onclick="analyzeFile()">Analisar</button>
  </section>
  <section id="results"></section>
</main>
<script>
mermaid.initialize({ startOnLoad: false, theme: "default" });
async function loadStats() {
  const response = await fetch("/v1/diagramas/stats");
  const payload = await response.json();
  const data = payload.data || {};
  const byType = data.by_type || {};
  document.getElementById("stats").innerHTML = [
    ["Total", data.total || 0],
    ["Class", byType.class || 0],
    ["Flowchart", byType.flowchart || 0],
    ["BPMN", data.automatic_server?.status === "available" ? "Ativo" : "Indisponivel"],
    ["Versionamento", data.automatic_server?.version_history ? "Ativo" : "Indisponivel"],
  ].map(([label, value]) => `<article class="card"><span>${label}</span><div class="stat">${value}</div></article>`).join("");
}
async function analyzeFile() {
  const file = document.getElementById("fileInput").files[0];
  if (!file) return;
  const response = await fetch("/v1/diagramas/analisar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, content: await file.text() })
  });
  const payload = await response.json();
  const result = payload.data || {};
  const diagrams = [
    ["Class Diagram", result.class_diagram],
    ["Flowchart", result.flowchart],
    ["Arquitetura Hexagonal", result.hexagonal],
  ].filter(([, diagram]) => diagram);
  document.getElementById("results").innerHTML = `<section class="card"><h2>${file.name}</h2>${diagrams.map(([title, diagram]) => `<h3>${title}</h3><div class="mermaid">${diagram}</div>`).join("")}</section>`;
  await mermaid.run({ querySelector: ".mermaid" });
}
loadStats();
setInterval(loadStats, 5000);
</script>
</body>
</html>"""
    )
