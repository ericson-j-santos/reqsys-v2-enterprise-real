from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/hosted_worker_pool_reqsys_task.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hosted_worker_pool_reqsys_task", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_tree(tmp_path: Path) -> Path:
    for relative in (
        "AGENTS.md",
        ".github/workflows/codex-worker-pool-handoff.yml",
        "scripts/pending_development_worker_pool_bridge.py",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative + "\n", encoding="utf-8")
    return tmp_path


def test_receipt_is_real_bounded_and_non_mutating(tmp_path: Path) -> None:
    module = load_module()
    root = source_tree(tmp_path)
    result = module.receipt(root, issue_number=2020, request_id="reqsys:2020:main",
                            base_sha="a" * 40)

    assert result["result"] == "REQSYS_HOSTED_WORKER_TASK_EXECUTED"
    assert result["simulated"] is False
    assert result["source_modified"] is False
    assert result["production_touched"] is False
    assert result["deploy_executed"] is False
    assert result["merge_executed"] is False
    assert set(result["inputs"]) == set(module.INPUTS)


def test_receipt_detects_tampering(tmp_path: Path) -> None:
    module = load_module()
    root = source_tree(tmp_path)
    original = module.receipt(root, issue_number=2020, request_id="stable",
                              base_sha="b" * 40)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(original), encoding="utf-8")

    (root / "AGENTS.md").write_text("changed\n", encoding="utf-8")

    assert module.read_json(receipt) != module.receipt(
        root, issue_number=2020, request_id="stable", base_sha="b" * 40
    )


def test_rejects_symlinked_source_input(tmp_path: Path) -> None:
    module = load_module()
    root = source_tree(tmp_path)
    target = tmp_path / "target"
    target.write_text("replacement", encoding="utf-8")
    workflow = root / ".github/workflows/codex-worker-pool-handoff.yml"
    workflow.unlink()
    workflow.symlink_to(target)

    try:
        module.receipt(root, issue_number=2020, request_id="stable", base_sha="c" * 40)
    except module.TaskError as exc:
        assert str(exc) == "task_input_invalid"
    else:
        raise AssertionError("symlinked input should be rejected")
