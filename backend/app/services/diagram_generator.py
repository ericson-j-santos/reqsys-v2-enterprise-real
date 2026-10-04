"""Compatibilidade do backend para o gerador portatil.

O nucleo vive em ``diagram_generator_portable`` para poder ser empacotado e
executado em outro computador sem depender do backend ReqSys.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
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
