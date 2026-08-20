from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_gitlab_mirror.py"
SPEC = importlib.util.spec_from_file_location("sync_gitlab_mirror", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_classify_state_in_sync() -> None:
    assert MODULE.classify_state(
        source_sha="abc",
        target_sha="abc",
        target_is_ancestor=True,
    ) == "in_sync"


def test_classify_state_fast_forward() -> None:
    assert MODULE.classify_state(
        source_sha="new",
        target_sha="old",
        target_is_ancestor=True,
    ) == "fast_forward"


def test_classify_state_diverged_fail_closed() -> None:
    assert MODULE.classify_state(
        source_sha="github",
        target_sha="gitlab-exclusive",
        target_is_ancestor=False,
    ) == "diverged"
