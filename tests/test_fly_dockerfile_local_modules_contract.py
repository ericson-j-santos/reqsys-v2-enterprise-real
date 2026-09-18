import ast
from pathlib import Path

BACKEND = Path("backend")
DOCKERFILE = BACKEND / "Dockerfile.fly"

# Entradas de backend/ que nao sao modulos/pacotes Python a serem embarcados na
# imagem Fly (config de build, docs, testes, migrations, etc.).
NON_RUNTIME_ENTRIES = {
    "Dockerfile",
    "Dockerfile.fly",
    "alembic.ini",
    "alembic",
    "app",
    "config",
    "data",
    "docker-compose.operational-worker.yml",
    "fly.dev.toml",
    "fly.staging.toml",
    "fly.toml",
    "fly_boot.sh",
    "migrations",
    "ocr_tests",
    "pyproject.toml",
    "requirements-audit.txt",
    "requirements-rag.txt",
    "requirements.txt",
    "ruff.toml",
    "scripts_audit",
    "tests",
}


def _copied_targets() -> set[str]:
    """Nomes de topo em backend/ que o Dockerfile.fly copia para /app."""
    targets = set()
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("COPY "):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        targets.add(parts[1])
    return targets


def _copia_tudo() -> bool:
    """True se o Dockerfile.fly usa `COPY . .` (todo o contexto de build)."""
    return "." in _copied_targets()


def _local_sibling_candidates() -> dict[str, str]:
    """Mapeia nome importavel (sem extensao) -> entrada real em backend/."""
    candidates: dict[str, str] = {}
    for entry in BACKEND.iterdir():
        if entry.name in NON_RUNTIME_ENTRIES or entry.name.startswith("."):
            continue
        if entry.is_dir() and (entry / "__init__.py").is_file():
            candidates[entry.name] = entry.name
        elif entry.is_file() and entry.suffix == ".py":
            candidates[entry.stem] = entry.name
    return candidates


def _imported_top_level_names(candidates: set[str]) -> set[str]:
    """Nomes de `candidates` importados em qualquer arquivo sob backend/app."""
    found: set[str] = set()
    for py_file in (BACKEND / "app").rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in candidates:
                        found.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in candidates:
                        found.add(top)
    return found


def test_dockerfile_fly_copia_todo_modulo_local_importado_pelo_app() -> None:
    """Evita o padrao de incidente ocr_evidencia (2026-08-24) e
    wsjf_workbook_package (2026-09-09): um pacote/modulo local novo em
    backend/ e importado por backend/app, mas backend/Dockerfile.fly nao e
    atualizado para copia-lo, causando ModuleNotFoundError em crash loop no
    Fly (dev/staging/prod usam o mesmo Dockerfile.fly).

    Desde a correcao de 2026-09-09 o Dockerfile.fly usa `COPY . .` (com
    .dockerignore como denylist) em vez de uma allowlist por modulo, o que ja
    elimina essa classe de bug na raiz. Este teste continua existindo como
    guarda de regressao: se alguem voltar para uma allowlist explicita no
    futuro, ele volta a checar modulo por modulo.
    """
    if _copia_tudo():
        return

    candidates = _local_sibling_candidates()
    imported = _imported_top_level_names(set(candidates))
    copied = _copied_targets()

    missing = sorted(
        name
        for name in imported
        if candidates[name] not in copied
    )

    assert not missing, (
        "backend/Dockerfile.fly nao copia modulo(s) local(is) importado(s) por "
        f"backend/app: {missing}. Adicione "
        "`COPY <entrada-em-backend/> /app/<entrada-em-backend/>` no Dockerfile.fly, "
        "ou volte a usar `COPY . .` (com .dockerignore) para eliminar a classe "
        "inteira de bug em vez de corrigir modulo a modulo."
    )
