"""Modulo autocontido para gerar diagramas Mermaid a partir de Python.

Nao depende de FastAPI, SQLAlchemy ou do pacote app. Pode ser copiado para
outro computador e executado apenas com a biblioteca padrao do Python 3.11+.
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class DiagramType(str, Enum):
    FLOWCHART = "flowchart"
    CLASS = "class"
    HEXAGONAL = "hexagonal"


@dataclass(frozen=True)
class DiagramVersion:
    diagram_id: str
    content_hash: str
    generated_at: datetime
    diagram_type: DiagramType
    filepath: str
    adr_references: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CodeAnalysis:
    filepath: str
    functions: list[dict[str, Any]]
    classes: list[dict[str, Any]]
    imports: list[str]
    interfaces: list[dict[str, Any]]
    adapters: list[dict[str, Any]]
    domain_classes: list[dict[str, Any]]


class ASTAnalyzer:
    class _Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.functions: list[dict[str, Any]] = []
            self.classes: list[dict[str, Any]] = []
            self.imports: list[str] = []
            self.interfaces: list[dict[str, Any]] = []
            self.adapters: list[dict[str, Any]] = []
            self.domain_classes: list[dict[str, Any]] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._append_function(node, is_async=False)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._append_function(node, is_async=True)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            bases = [_node_name(base) for base in node.bases]
            methods = [
                item.name
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
            ]
            class_info = {
                "name": node.name,
                "bases": bases,
                "methods": methods,
                "line": node.lineno,
                "is_port": self._is_port(node, bases),
                "is_adapter": self._is_adapter(node, bases),
                "is_domain": False,
            }
            class_info["is_domain"] = (
                not class_info["is_port"]
                and not class_info["is_adapter"]
                and not self._is_infrastructure(node.name)
            )

            self.classes.append(class_info)
            if class_info["is_port"]:
                self.interfaces.append(class_info)
            elif class_info["is_adapter"]:
                self.adapters.append(class_info)
            elif class_info["is_domain"]:
                self.domain_classes.append(class_info)
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            self.imports.extend(alias.name for alias in node.names)
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            module = node.module or ""
            for alias in node.names:
                self.imports.append(f"{module}.{alias.name}" if module else alias.name)
            self.generic_visit(node)

        def _append_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool) -> None:
            self.functions.append(
                {
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [_node_name(decorator) for decorator in node.decorator_list],
                    "line": node.lineno,
                    "is_async": is_async,
                }
            )

        @staticmethod
        def _is_port(node: ast.ClassDef, bases: list[str]) -> bool:
            base_names = {base.rsplit(".", 1)[-1] for base in bases}
            return bool({"ABC", "Protocol"} & base_names) or node.name.endswith(("Port", "Gateway"))

        @staticmethod
        def _is_adapter(node: ast.ClassDef, bases: list[str]) -> bool:
            names = [node.name, *bases]
            return any("adapter" in name.lower() for name in names)

        @staticmethod
        def _is_infrastructure(name: str) -> bool:
            return name.endswith(("Controller", "Repository", "Config", "Settings"))

    def analyze(self, filepath: str | Path) -> CodeAnalysis:
        path = Path(filepath)
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except UnicodeDecodeError:
            source = path.read_text(encoding="latin-1")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            raise ValueError(f"Erro de sintaxe em {path}: {exc}") from exc

        visitor = self._Visitor()
        visitor.visit(tree)
        return CodeAnalysis(
            filepath=str(path),
            functions=visitor.functions,
            classes=visitor.classes,
            imports=visitor.imports,
            interfaces=visitor.interfaces,
            adapters=visitor.adapters,
            domain_classes=visitor.domain_classes,
        )


class MermaidGenerator:
    def generate_flowchart(self, analysis: CodeAnalysis) -> str | None:
        if not analysis.functions:
            return None
        function = analysis.functions[0]
        return "\n".join(
            [
                "flowchart TD",
                f"    A([START: {function['name']}])",
                "    B[Processar entrada]",
                "    C{Resultado valido?}",
                "    D[Retornar sucesso]",
                "    E[Retornar erro controlado]",
                "    A --> B",
                "    B --> C",
                "    C -->|sim| D",
                "    C -->|nao| E",
            ]
        )

    def generate_class_diagram(self, analysis: CodeAnalysis) -> str | None:
        if not analysis.classes:
            return None
        lines = ["classDiagram"]
        for class_info in analysis.classes:
            lines.append(f"    class {class_info['name']} {{")
            for method in class_info["methods"]:
                lines.append(f"        {method}()")
            lines.append("    }")
            for base in class_info["bases"]:
                if base and base != "object":
                    lines.append(f"    {base} <|-- {class_info['name']}")
        return "\n".join(lines)

    def generate_hexagonal_diagram(self, analysis: CodeAnalysis) -> str | None:
        if not (analysis.interfaces or analysis.adapters or analysis.domain_classes):
            return None

        lines = ["graph TB"]
        if analysis.domain_classes:
            lines.append('    subgraph DOMAIN["Dominio"]')
            for item in analysis.domain_classes:
                lines.append(f'        {_node_id("D", item["name"])}["{item["name"]}"]')
            lines.append("    end")
        if analysis.interfaces:
            lines.append('    subgraph PORTS["Portas"]')
            for item in analysis.interfaces:
                lines.append(f'        {_node_id("P", item["name"])}["{item["name"]}"]')
            lines.append("    end")
        if analysis.adapters:
            lines.append('    subgraph ADAPTERS["Adaptadores"]')
            for item in analysis.adapters:
                lines.append(f'        {_node_id("A", item["name"])}["{item["name"]}"]')
            lines.append("    end")
        if analysis.interfaces and analysis.domain_classes:
            lines.append("    PORTS --> DOMAIN")
        if analysis.adapters and analysis.interfaces:
            lines.append("    ADAPTERS --> PORTS")
        return "\n".join(lines)

    def generate(self, analysis: CodeAnalysis, diagram_type: DiagramType) -> str | None:
        if diagram_type == DiagramType.FLOWCHART:
            return self.generate_flowchart(analysis)
        if diagram_type == DiagramType.CLASS:
            return self.generate_class_diagram(analysis)
        if diagram_type == DiagramType.HEXAGONAL:
            return self.generate_hexagonal_diagram(analysis)
        return None


class FileDiagramRepository:
    def __init__(self, diagrams_dir: str | Path = ".diagrams") -> None:
        self.diagrams_dir = Path(diagrams_dir)
        self.versions_dir = self.diagrams_dir / ".versions"
        self.manifest_file = self.diagrams_dir / "manifest.json"
        self.diagrams_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def save_diagram(self, diagram_id: str, content: str, version: DiagramVersion) -> bool:
        safe_id = _safe_id(diagram_id)
        output_file = self.diagrams_dir / f"{safe_id}.md"
        if output_file.exists():
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            shutil.copyfile(output_file, self.versions_dir / f"{safe_id}_{timestamp}.md")

        output_file.write_text(f"```mermaid\n{content}\n```\n", encoding="utf-8")
        manifest = self._load_manifest()
        manifest.setdefault("diagrams", {})[diagram_id] = {
            "safe_id": safe_id,
            "filename": output_file.name,
            "filepath": version.filepath,
            "diagram_type": version.diagram_type.value,
            "content_hash": version.content_hash,
            "generated_at": version.generated_at.isoformat(),
            "adr_references": version.adr_references,
        }
        manifest["last_updated"] = version.generated_at.isoformat()
        self._save_manifest(manifest)
        return True

    def get_diagram(self, diagram_id: str) -> str | None:
        entry = self._load_manifest().get("diagrams", {}).get(diagram_id)
        filename = entry.get("filename") if isinstance(entry, dict) else f"{_safe_id(diagram_id)}.md"
        file = self.diagrams_dir / filename
        return file.read_text(encoding="utf-8") if file.exists() else None

    def list_diagrams(self) -> dict[str, Any]:
        return self._load_manifest()

    def is_idempotent(self, diagram_id: str, new_hash: str) -> bool:
        entry = self._load_manifest().get("diagrams", {}).get(diagram_id)
        return isinstance(entry, dict) and entry.get("content_hash") == new_hash

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_file.exists():
            return {"diagrams": {}, "last_updated": None}
        return json.loads(self.manifest_file.read_text(encoding="utf-8"))

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self.manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


class DiagramGenerationUseCase:
    def __init__(
        self,
        analyzer: ASTAnalyzer | None = None,
        generator: MermaidGenerator | None = None,
        repository: FileDiagramRepository | None = None,
    ) -> None:
        self.analyzer = analyzer or ASTAnalyzer()
        self.generator = generator or MermaidGenerator()
        self.repository = repository or FileDiagramRepository()

    def execute(
        self,
        filepath: str | Path,
        diagram_types: list[DiagramType],
        correlation_id: str = "local",
    ) -> dict[str, Any]:
        analysis = self.analyzer.analyze(filepath)
        results: dict[str, Any] = {}

        for diagram_type in diagram_types:
            diagram_id = f"{Path(filepath).as_posix()}::{diagram_type.value}"
            content = self.generator.generate(analysis, diagram_type)
            if not content:
                results[diagram_id] = {"changed": False, "reason": "empty"}
                continue

            content_hash = _hash(content)
            if self.repository.is_idempotent(diagram_id, content_hash):
                results[diagram_id] = {"changed": False, "reason": "idempotent"}
                continue

            version = DiagramVersion(
                diagram_id=diagram_id,
                content_hash=content_hash,
                generated_at=datetime.now(UTC),
                diagram_type=diagram_type,
                filepath=str(filepath),
                adr_references=["ADR-001", "ADR-003"],
            )
            saved = self.repository.save_diagram(diagram_id, content, version)
            results[diagram_id] = {
                "changed": saved,
                "content_hash": content_hash,
                "correlation_id": correlation_id,
            }
        return results


def diagram_types_from_option(option: str) -> list[DiagramType]:
    if option == "all":
        return [DiagramType.FLOWCHART, DiagramType.CLASS, DiagramType.HEXAGONAL]
    return [DiagramType(option)]


def scan_python_files(path: str | Path) -> list[Path]:
    root = Path(path)
    ignored_parts = {".git", ".venv", "venv", "__pycache__", "node_modules", ".diagrams", "alembic"}
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    return sorted(
        file
        for file in root.rglob("*.py")
        if not any(part in ignored_parts for part in file.parts)
    )


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _safe_id(value: str) -> str:
    digest = _hash(value)
    readable = "".join(char if char.isalnum() else "-" for char in value)[:96].strip("-")
    return f"{readable}-{digest}" if readable else digest


def _node_id(prefix: str, value: str) -> str:
    return f"{prefix}{hashlib.sha1(value.encode('utf-8')).hexdigest()[:8]}"


def _node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _node_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Subscript):
        return _node_name(node.value)
    if isinstance(node, ast.Call):
        return _node_name(node.func)
    return ""
