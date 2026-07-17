from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parents[1]
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from app.main import app


DEFAULT_OUTPUT = "../docs-site/assets/openapi/reqsys-runtime-openapi-v0.6.0.json"
DIAGNOSTIC_DIR = ".tmp/openapi-diff"
VOLATILE_OPENAPI_KEYS = {"title"}


def gerar_openapi() -> dict[str, Any]:
    schema = app.openapi()
    schema.setdefault("info", {})["x-reqsys-generated-by"] = "runtime/scripts/export_openapi.py"
    schema.setdefault("info", {})["x-reqsys-contract-source"] = "runtime-fastapi"
    schema.setdefault("info", {})["x-reqsys-contract-mode"] = "canonical-generated"
    return schema


def normalizar_contrato(value: Any) -> Any:
    """Remove apenas metadados descritivos voláteis do gerador.

    Paths, tipos, formatos, campos obrigatórios, constraints, enums, respostas e
    extensões ReqSys continuam sendo comparados integralmente.
    """
    if isinstance(value, dict):
        return {
            key: normalizar_contrato(item)
            for key, item in value.items()
            if key not in VOLATILE_OPENAPI_KEYS
        }
    if isinstance(value, list):
        return [normalizar_contrato(item) for item in value]
    return value


def serializar_json(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def escrever_json(path: Path, schema: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serializar_json(schema), encoding="utf-8")


def carregar_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def gerar_diff(atual: dict[str, Any], gerado: dict[str, Any], output_path: Path) -> str:
    atual_normalizado = normalizar_contrato(atual)
    gerado_normalizado = normalizar_contrato(gerado)
    return "\n".join(
        difflib.unified_diff(
            serializar_json(atual_normalizado).splitlines(),
            serializar_json(gerado_normalizado).splitlines(),
            fromfile=str(output_path),
            tofile="runtime-generated-openapi.normalized.json",
            lineterm="",
        )
    ) + "\n"


def escrever_diagnostico(runtime_dir: Path, atual: dict[str, Any], gerado: dict[str, Any], output_path: Path) -> None:
    diagnostic_dir = runtime_dir / DIAGNOSTIC_DIR
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    escrever_json(diagnostic_dir / "canonical-openapi.json", atual)
    escrever_json(diagnostic_dir / "generated-openapi.json", gerado)
    diff_text = gerar_diff(atual, gerado, output_path)
    (diagnostic_dir / "openapi.diff").write_text(diff_text, encoding="utf-8")
    print(diff_text, file=sys.stderr, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta o OpenAPI canônico gerado pelo FastAPI runtime.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Arquivo de saída do contrato OpenAPI canônico.")
    parser.add_argument("--check", action="store_true", help="Valida semanticamente o contrato OpenAPI canônico.")
    args = parser.parse_args()

    output_path = (RUNTIME_DIR / args.output).resolve()
    schema = gerar_openapi()

    if args.check:
        if not output_path.exists():
            print(f"Contrato OpenAPI não encontrado: {output_path}", file=sys.stderr)
            return 2
        atual = carregar_json(output_path)
        if normalizar_contrato(atual) != normalizar_contrato(schema):
            print("Contrato OpenAPI semanticamente divergente do runtime FastAPI.", file=sys.stderr)
            escrever_diagnostico(RUNTIME_DIR, atual, schema, output_path)
            return 1
        print(f"Contrato OpenAPI semanticamente sincronizado: {output_path}")
        return 0

    escrever_json(output_path, schema)
    print(f"Contrato OpenAPI exportado: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
