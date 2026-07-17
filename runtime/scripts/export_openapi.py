from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

from app.main import app


DEFAULT_OUTPUT = "../docs-site/assets/openapi/reqsys-runtime-openapi-v0.6.0.json"


def gerar_openapi() -> dict[str, Any]:
    schema = app.openapi()
    schema.setdefault("info", {})["x-reqsys-generated-by"] = "runtime/scripts/export_openapi.py"
    schema.setdefault("info", {})["x-reqsys-contract-source"] = "runtime-fastapi"
    schema.setdefault("info", {})["x-reqsys-contract-mode"] = "canonical-generated"
    return schema


def serializar_json(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def escrever_json(path: Path, schema: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serializar_json(schema), encoding="utf-8")


def carregar_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def imprimir_diff(atual: dict[str, Any], gerado: dict[str, Any], output_path: Path) -> None:
    diff = difflib.unified_diff(
        serializar_json(atual).splitlines(),
        serializar_json(gerado).splitlines(),
        fromfile=str(output_path),
        tofile="runtime-generated-openapi.json",
        lineterm="",
    )
    for linha in diff:
        print(linha, file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta o OpenAPI canônico gerado pelo FastAPI runtime.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Arquivo de saída do contrato OpenAPI canônico.")
    parser.add_argument("--check", action="store_true", help="Valida se o arquivo canônico está sincronizado.")
    args = parser.parse_args()

    runtime_dir = Path(__file__).resolve().parents[1]
    output_path = (runtime_dir / args.output).resolve()
    schema = gerar_openapi()

    if args.check:
        if not output_path.exists():
            print(f"Contrato OpenAPI não encontrado: {output_path}", file=sys.stderr)
            return 2
        atual = carregar_json(output_path)
        if atual != schema:
            print("Contrato OpenAPI divergente do runtime FastAPI. Execute export_openapi.py e versione o resultado.", file=sys.stderr)
            imprimir_diff(atual, schema, output_path)
            return 1
        print(f"Contrato OpenAPI sincronizado: {output_path}")
        return 0

    escrever_json(output_path, schema)
    print(f"Contrato OpenAPI exportado: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
