from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_pr_creation_paths.py"
SPEC = importlib.util.spec_from_file_location("validate_pr_creation_paths", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _workflow(tmp_path: Path, name: str, content: str) -> None:
    directory = tmp_path / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content, encoding="utf-8")


def test_blocks_direct_gh_pr_create_to_main(tmp_path: Path) -> None:
    _workflow(
        tmp_path,
        "bad.yml",
        """name: bad
jobs:
  x:
    steps:
      - run: |
          gh pr create \\
            --base main \\
            --head automation/x
""",
    )
    report = MODULE.validate(tmp_path)
    assert report["valid"] is False
    assert report["violations"][0]["path"] == ".github/workflows/bad.yml"


def test_blocks_direct_rest_post_to_main(tmp_path: Path) -> None:
    _workflow(
        tmp_path,
        "bad-api.yml",
        """name: bad
jobs:
  x:
    steps:
      - run: |
          echo '{"title":"x","head":"b","base":"main"}' > request.json
          gh api --method POST "repos/o/r/pulls" --input request.json
""",
    )
    assert MODULE.validate(tmp_path)["valid"] is False


def test_does_not_block_non_main_promotion(tmp_path: Path) -> None:
    _workflow(
        tmp_path,
        "homolog.yml",
        """name: homolog
jobs:
  x:
    steps:
      - run: |
          gh pr create --base homolog --head dev --title x --body y
""",
    )
    assert MODULE.validate(tmp_path)["valid"] is True


def test_repository_has_no_direct_main_pr_creator() -> None:
    report = MODULE.validate(ROOT)
    assert report["valid"] is True, report["violations"]
