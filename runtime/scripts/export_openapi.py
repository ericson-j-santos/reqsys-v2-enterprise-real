from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.main import app


DEFAULT_OUTPUT = "../docs-site/assets/openapi/reqsys-runtime-openapi-v0.5.0.generated.json"


def gerar_openapi() -> dict[str, Any]:
    schema = app.openapi()
    schema.setdefault("info", {})["x-reqsys-generated-by"] = "runtime/scripts/export_openapi.py"
    schema.setdefault("info", {})["x-reqsys-contract-source"] = "runtime-fastapi"
    return schema


def escrever_json(path: Path, schema: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def carregar_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta o OpenAPI gerado pelo FastAPI runtime.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Arquivo de saída do contrato OpenAPI.")
    parser.add_argument("--check", action="store_true", help="Valida se o arquivo versionado está sincronizado.")
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
            return 1
        print(f"Contrato OpenAPI sincronizado: {output_path}")
        return 0

    escrever_json(output_path, schema)
    print(f"Contrato OpenAPI exportado: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
