"""Compatibilidade do backend para o gerador portatil.

O nucleo vive em ``diagram_generator_portable`` para poder ser empacotado e
executado em outro computador sem depender do backend ReqSys.
"""

import sys
from pathlib import Path


def _localizar_repo_root() -> Path:
    """Sobe os diretorios ancestrais ate achar quem contem diagram_generator_portable.

    Independente da profundidade de backend/app/services relativa a raiz do
    projeto (repo local, imagem Docker que remove o prefixo backend/, ou uma
    copia parcial de backend/ para outro PC), evita assumir um numero fixo de
    niveis (ver ADR-035).
    """
    for candidato in Path(__file__).resolve().parents:
        if (candidato / "diagram_generator_portable" / "__init__.py").is_file():
            return candidato
    raise ModuleNotFoundError(
        "Pasta 'diagram_generator_portable' nao encontrada em nenhum diretorio "
        f"ancestral de {Path(__file__).resolve()}. Copie essa pasta junto do "
        "backend para que o gerador de diagramas funcione."
    )


_REPO_ROOT = _localizar_repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from diagram_generator_portable import (  # noqa: E402,F401
    ASTAnalyzer,
    CodeAnalysis,
    DiagramGenerationUseCase,
    DiagramType,
    DiagramVersion,
    FileDiagramRepository,
    MermaidGenerator,
    diagram_types_from_option,
    scan_python_files,
)
