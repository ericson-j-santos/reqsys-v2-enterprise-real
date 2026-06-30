from pathlib import Path

import pytest

from app.testing.repository_paths import get_repository_root, resolve_repo_file


def test_get_repository_root_from_repo_root_file_context():
    root = get_repository_root(start=__file__)

    assert (root / '.github').is_dir()
    assert (root / 'backend').is_dir()


def test_get_repository_root_from_backend_directory_context():
    root = get_repository_root()
    backend_dir = root / 'backend'

    resolved = get_repository_root(start=backend_dir)

    assert resolved == root


def test_resolve_repo_file_returns_existing_workflow_path():
    workflow_path = resolve_repo_file('.github', 'workflows', 'power-automate-flow-provisioning-p0.yml')

    assert workflow_path.exists()
    assert workflow_path.name == 'power-automate-flow-provisioning-p0.yml'


def test_resolve_repo_file_rejects_missing_file_when_required():
    with pytest.raises(AssertionError):
        resolve_repo_file('arquivo-inexistente.reqsys')


def test_resolve_repo_file_allows_missing_file_when_not_required():
    path = resolve_repo_file('arquivo-inexistente.reqsys', must_exist=False)

    assert isinstance(path, Path)
    assert path.name == 'arquivo-inexistente.reqsys'


def test_resolve_repo_file_rejeita_partes_vazias():
    with pytest.raises(ValueError):
        resolve_repo_file()


def test_get_repository_root_via_sentinela_pyproject(tmp_path, monkeypatch):
    fake_repo = tmp_path / 'fake-repo'
    fake_repo.mkdir()
    (fake_repo / 'pyproject.toml').write_text('[project]\nname="reqsys"\n', encoding='utf-8')
    (fake_repo / 'backend').mkdir()

    resolved = get_repository_root(start=fake_repo / 'backend' / 'app')

    assert resolved == fake_repo


def test_get_repository_root_via_git_e_backend(tmp_path):
    fake_repo = tmp_path / 'git-repo'
    fake_repo.mkdir()
    (fake_repo / '.git').mkdir()
    (fake_repo / 'backend').mkdir()

    resolved = get_repository_root(start=fake_repo / 'backend')

    assert resolved == fake_repo
