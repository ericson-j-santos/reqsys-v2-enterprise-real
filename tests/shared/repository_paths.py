from pathlib import Path


_REPO_SENTINELS = (
    '.git',
    '.github',
    'pyproject.toml',
    'README.md',
)


def get_repository_root(start: Path | str | None = None) -> Path:
    """Resolve a raiz do repositorio independentemente do cwd do pytest.

    O helper evita falsos negativos quando suites executam a partir da raiz,
    de `backend/` ou de outros diretórios de trabalho em runners distintos.
    """
    current = Path(start or __file__).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / '.github').is_dir() and (candidate / 'backend').is_dir():
            return candidate
        if (candidate / '.git').exists() and (candidate / 'backend').is_dir():
            return candidate
        if all((candidate / sentinel).exists() for sentinel in ('pyproject.toml', 'backend')):
            return candidate

    sentinels = ', '.join(_REPO_SENTINELS)
    raise AssertionError(f'Nao foi possivel resolver a raiz do repositorio usando sentinelas: {sentinels}')


def resolve_repo_file(*parts: str, start: Path | str | None = None, must_exist: bool = True) -> Path:
    """Resolve um arquivo relativo a raiz do repositorio.

    Args:
        *parts: partes do caminho dentro do repositorio.
        start: ponto inicial opcional para busca da raiz.
        must_exist: quando True, falha se o arquivo nao existir.
    """
    if not parts:
        raise ValueError('Informe ao menos uma parte de caminho')

    path = get_repository_root(start=start).joinpath(*parts)
    if must_exist and not path.exists():
        raise AssertionError(f'Arquivo esperado nao encontrado no repositorio: {path}')
    return path
