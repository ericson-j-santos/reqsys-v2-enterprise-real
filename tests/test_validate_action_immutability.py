from pathlib import Path

from scripts import validate_action_immutability as gate


SHA = "0123456789abcdef0123456789abcdef01234567"
DIGEST = "sha256:" + ("a" * 64)


def write_workflow(root: Path, name: str, uses: str) -> str:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "name: test\non: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        f"    steps:\n      - uses: {uses}\n",
        encoding="utf-8",
    )
    return path.relative_to(root).as_posix()


def test_local_action_is_explicit_exception(tmp_path: Path) -> None:
    rel = write_workflow(tmp_path, "local.yml", "./.github/actions/internal")
    assert gate.scan(tmp_path, [rel]) == []


def test_external_action_full_sha_is_allowed(tmp_path: Path) -> None:
    rel = write_workflow(tmp_path, "pinned.yml", f"actions/checkout@{SHA}")
    assert gate.scan(tmp_path, [rel]) == []


def test_external_tag_is_blocked(tmp_path: Path) -> None:
    rel = write_workflow(tmp_path, "mutable.yml", "actions/checkout@v4")
    findings = gate.scan(tmp_path, [rel])
    assert len(findings) == 1
    assert findings[0].reason == "external_action_ref_is_mutable"


def test_master_ref_is_blocked(tmp_path: Path) -> None:
    rel = write_workflow(tmp_path, "master.yml", "vendor/action@master")
    findings = gate.scan(tmp_path, [rel])
    assert len(findings) == 1
    assert findings[0].uses == "vendor/action@master"


def test_external_reusable_workflow_requires_sha(tmp_path: Path) -> None:
    rel = write_workflow(tmp_path, "reusable.yml", "owner/repo/.github/workflows/reuse.yml@v2")
    assert gate.scan(tmp_path, [rel])[0].reason == "external_action_ref_is_mutable"


def test_docker_reference_requires_sha256_digest(tmp_path: Path) -> None:
    bad = write_workflow(tmp_path, "docker-tag.yml", "docker://alpine:3.20")
    good = write_workflow(tmp_path, "docker-digest.yml", f"docker://alpine@{DIGEST}")
    assert gate.scan(tmp_path, [bad])[0].reason == "docker_image_not_pinned_by_digest"
    assert gate.scan(tmp_path, [good]) == []


def test_scan_blocks_all_mutable_refs_in_touched_workflow(tmp_path: Path) -> None:
    path = tmp_path / ".github" / "workflows" / "mixed.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "name: mixed\non: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        f"    steps:\n      - uses: actions/checkout@{SHA}\n      - uses: actions/setup-python@v5\n",
        encoding="utf-8",
    )
    findings = gate.scan(tmp_path, [path.relative_to(tmp_path).as_posix()])
    assert [(item.line, item.uses) for item in findings] == [(8, "actions/setup-python@v5")]


def test_negative_self_test_proves_gate_detects_mutable_ref() -> None:
    assert gate.self_test_negative() is True
