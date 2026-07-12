from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.envelope import ok
from app.services.diagram_generator import (
    ASTAnalyzer,
    DiagramGenerationUseCase,
    FileDiagramRepository,
    MermaidGenerator,
    diagram_types_from_option,
)

router = APIRouter(prefix="/v1/diagramas", tags=["Arquitetura Viva"])

_repository = FileDiagramRepository()
_analyzer = ASTAnalyzer()
_generator = MermaidGenerator()
_usecase = DiagramGenerationUseCase(_analyzer, _generator, _repository)


class CodeAnalysisRequest(BaseModel):
    filename: str
    content: str


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
        }
    )


@router.get("/health")
def health():
    return ok({"status": "healthy", "service": "diagram-generator", "version": "1.0.0"})


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
    code { color: #334155; word-break: break-all; }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>ReqSys Arquitetura Viva</h1>
      <p>Diagramas Mermaid gerados a partir do codigo Python.</p>
    </div>
    <a href="/v1/diagramas/stats">Stats JSON</a>
  </header>
  <section class="grid" id="stats"></section>
  <section class="card">
    <h2>Analisar arquivo</h2>
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
    ["Hexagonal", byType.hexagonal || 0],
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
