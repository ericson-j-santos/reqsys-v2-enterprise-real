from __future__ import annotations

import argparse
import json
import logging

from .core import (
    DiagramGenerationUseCase,
    FileDiagramRepository,
    diagram_types_from_option,
    scan_python_files,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gerador Mermaid portatil")
    parser.add_argument("--path", default=".", help="Diretorio ou arquivo Python para analisar")
    parser.add_argument("--file", help="Arquivo Python especifico")
    parser.add_argument("--type", "--types", dest="types", default="all", choices=["flowchart", "class", "hexagonal", "all"])
    parser.add_argument("--diagrams-dir", default=".diagrams", help="Diretorio de saida dos diagramas")
    parser.add_argument("--show-versions", action="store_true", help="Exibe o manifest de versoes")
    parser.add_argument("--correlation-id", default="portable-local", help="Identificador de rastreabilidade")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = FileDiagramRepository(args.diagrams_dir)

    if args.show_versions:
        print(json.dumps(repository.list_diagrams(), indent=2, ensure_ascii=False))
        return 0

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    usecase = DiagramGenerationUseCase(repository=repository)
    diagram_types = diagram_types_from_option(args.types)
    target = args.file or args.path
    changed = 0
    processed = 0

    for file in scan_python_files(target):
        processed += 1
        logging.info("analisando %s", file)
        results = usecase.execute(file, diagram_types, correlation_id=args.correlation_id)
        changed += sum(1 for result in results.values() if result.get("changed"))

    logging.info("%s arquivos analisados, %s diagramas atualizados", processed, changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
