#!/usr/bin/env python3
"""Valida o snapshot local OCR contra o engine pinado, sem permitir drift executável."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


class ParityError(RuntimeError):
    pass


EXPECTED_REPOSITORY = "ericson-j-santos/ocr-evidence-engine"
EXPECTED_VERSION = "1.2.0"
ALLOWED_NON_PYTHON = {"PROVENANCE.md"}
ROOT_INIT = "__init__.py"


def _fail(message: str) -> None:
    raise ParityError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if proc.returncode != 0:
        _fail("git_failed:" + " ".join(args) + ":" + proc.stderr.strip()[:250])
    return proc.stdout.strip()


def _load_lock(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    _require(data.get("repository") == EXPECTED_REPOSITORY, "lock_repository_mismatch")
    _require(data.get("version") == EXPECTED_VERSION, "lock_version_mismatch")
    sha = str(data.get("sha") or "")
    _require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "lock_sha_invalid")
    _require(data.get("module") == "ocr_evidencia", "lock_module_mismatch")
    return data


def _python_files(root: Path) -> dict[str, Path]:
    _require(root.is_dir(), f"package_root_missing:{root}")
    files: dict[str, Path] = {}
    for path in sorted(root.rglob("*.py")):
        _require(path.is_file() and not path.is_symlink(), f"python_file_invalid:{path}")
        rel = path.relative_to(root).as_posix()
        files[rel] = path
    _require(bool(files), f"python_files_missing:{root}")
    return files


def _assignment_value(tree: ast.Module, name: str) -> Any:
    found: list[Any] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    found.append(ast.literal_eval(node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            found.append(ast.literal_eval(node.value))
    _require(len(found) == 1, f"root_init_assignment_count:{name}:{len(found)}")
    return found[0]


def validate_root_init(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    tree = ast.parse(raw, filename=str(path))
    allowed_nodes: list[ast.stmt] = []
    for index, node in enumerate(tree.body):
        if (
            index == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        allowed_nodes.append(node)

    for node in allowed_nodes:
        _require(isinstance(node, (ast.Assign, ast.AnnAssign)), "root_init_executable_statement")
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets.append(node.target)
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        _require(names and set(names) <= {"__version__", "__all__"}, "root_init_unexpected_assignment")

    version = _assignment_value(tree, "__version__")
    exported = _assignment_value(tree, "__all__")
    _require(version == EXPECTED_VERSION, "root_init_version_mismatch")
    _require(exported == ["__version__"], "root_init_all_mismatch")
    return {"version": version, "all": exported}


def compare_python_tree(local_root: Path, engine_root: Path) -> dict[str, Any]:
    local = _python_files(local_root)
    engine = _python_files(engine_root)
    _require(set(local) == set(engine), "python_file_set_mismatch")

    byte_identical: list[str] = []
    for rel in sorted(local):
        if rel == ROOT_INIT:
            local_contract = validate_root_init(local[rel])
            engine_contract = validate_root_init(engine[rel])
            _require(local_contract == engine_contract, "root_init_contract_mismatch")
            continue
        left = local[rel].read_bytes()
        right = engine[rel].read_bytes()
        _require(left == right, f"python_drift:{rel}")
        byte_identical.append(rel)

    return {
        "python_files": sorted(local),
        "root_init_semantic_parity": True,
        "byte_identical_files": byte_identical,
    }


def _provenance_values(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    generator = re.search(r"SHA-256 do gerador de origem:\s*\`([0-9a-f]{64})\`", text)
    payload = re.search(r"SHA-256 do payload de origem:\s*\`([0-9a-f]{64})\`", text)
    _require(generator is not None, "provenance_generator_missing")
    _require(payload is not None, "provenance_payload_missing")
    _require("1.2.0" in text, "provenance_version_missing")
    return {
        "version": EXPECTED_VERSION,
        "generator_sha256": generator.group(1),
        "payload_sha256": payload.group(1),
    }


def validate_provenance(local_root: Path, engine_root: Path) -> dict[str, str]:
    local = local_root / "PROVENANCE.md"
    engine = engine_root / "PROVENANCE.md"
    _require(local.is_file() and engine.is_file(), "provenance_missing")
    left = _provenance_values(local)
    right = _provenance_values(engine)
    _require(left == right, "provenance_identity_mismatch")
    return left


def validate_non_python_surface(root: Path) -> None:
    extras = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix != ".py"
    }
    _require(extras == ALLOWED_NON_PYTHON, f"unexpected_non_python_files:{sorted(extras)}")


def validate_runtime_policy(reqsys_root: Path) -> dict[str, bool]:
    dockerfile = (reqsys_root / "backend/Dockerfile").read_text(encoding="utf-8")
    benchmark = (reqsys_root / ".github/workflows/ocr-benchmark.yml").read_text(encoding="utf-8")
    dev = (reqsys_root / ".github/workflows/fly-dev-fast-deploy.yml").read_text(encoding="utf-8")
    enterprise = (reqsys_root / ".github/workflows/fly-enterprise-sync.yml").read_text(encoding="utf-8")

    required_docker_tokens = (
        'ARG OCR_EXTERNAL_PACKAGE_REQUIRED=0',
        'rm -rf /app/ocr_evidencia',
        'site-packages',
        'OCR_ENGINE_SHA',
        'OCR_ENGINE_VERSION',
    )
    for token in required_docker_tokens:
        _require(token in dockerfile, "docker_external_contract_missing:" + token)

    for name, text in (("dev", dev), ("enterprise", enterprise)):
        _require("uses: ./.github/actions/prepare-ocr-runtime" in text, f"{name}_prepare_action_missing")
        _require("OCR_EXTERNAL_PACKAGE_REQUIRED=1" in text, f"{name}_external_required_missing")

    _require("external-package-contract:" in benchmark, "benchmark_external_contract_missing")
    _require("external-runtime-image-contract:" in benchmark, "benchmark_runtime_contract_missing")

    return {
        "docker_removes_local_copy_in_external_mode": True,
        "dev_requires_external_package": True,
        "enterprise_requires_external_package": True,
        "benchmark_external_contract_present": True,
    }


def validate(
    *,
    local_root: Path,
    engine_checkout: Path,
    lock_path: Path,
    reqsys_root: Path,
) -> dict[str, Any]:
    reqsys_root = reqsys_root.resolve()
    local_root = local_root.resolve()
    engine_checkout = engine_checkout.resolve()
    lock_path = lock_path.resolve()

    lock = _load_lock(lock_path)
    _require(engine_checkout.is_dir(), "engine_checkout_missing")
    actual_sha = _git(engine_checkout, "rev-parse", "HEAD")
    _require(actual_sha == lock["sha"], f"engine_sha_mismatch:{actual_sha}")
    _require(_git(engine_checkout, "status", "--porcelain") == "", "engine_checkout_dirty")

    engine_root = engine_checkout / "src/ocr_evidencia"
    tree = compare_python_tree(local_root, engine_root)
    provenance = validate_provenance(local_root, engine_root)
    validate_non_python_surface(local_root)
    runtime_policy = validate_runtime_policy(reqsys_root)

    local_digest = hashlib.sha256(
        "\n".join(
            f"{rel}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
            for rel, path in _python_files(local_root).items()
        ).encode("utf-8")
    ).hexdigest()
    engine_digest = hashlib.sha256(
        "\n".join(
            f"{rel}:{hashlib.sha256(path.read_bytes()).hexdigest()}"
            for rel, path in _python_files(engine_root).items()
        ).encode("utf-8")
    ).hexdigest()

    return {
        "schema_version": "1.0.0",
        "status": "OCR_LOCAL_FALLBACK_PARITY_VALIDATED",
        "repository": EXPECTED_REPOSITORY,
        "engine_sha": actual_sha,
        "version": EXPECTED_VERSION,
        "local_root": str(local_root),
        "engine_package_root": str(engine_root),
        "python_files": tree["python_files"],
        "byte_identical_files": tree["byte_identical_files"],
        "root_init_semantic_parity": tree["root_init_semantic_parity"],
        "provenance": provenance,
        "runtime_policy": runtime_policy,
        "local_python_tree_digest": local_digest,
        "engine_python_tree_digest": engine_digest,
        "digests_may_differ_only_due_to_root_init_docstring": local_digest != engine_digest,
        "production_uses_external_package": True,
        "local_snapshot_role": "DEV_TEST_OFFLINE_FALLBACK_ONLY",
        "production_touched": False,
        "pin_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", default="backend/ocr_evidencia")
    parser.add_argument("--engine-checkout", required=True)
    parser.add_argument("--lock", default="config/ocr-engine-lock.json")
    parser.add_argument("--reqsys-root", default=".")
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    try:
        report = validate(
            local_root=Path(args.local_root),
            engine_checkout=Path(args.engine_checkout),
            lock_path=Path(args.lock),
            reqsys_root=Path(args.reqsys_root),
        )
        raw = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(raw, encoding="utf-8")
        sys.stdout.write(raw)
        return 0
    except (ParityError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print("OCR_LOCAL_FALLBACK_PARITY_BLOCKED:" + str(exc)[:350], file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
