#!/usr/bin/env python3
"""Bloqueia referências mutáveis de Actions em workflows novos ou alterados.

O scanner sempre inventaria todos os workflows para medir a dívida histórica.
No modo changed, somente workflows novos/alterados em relação à base são
bloqueantes. Isso cria um ratchet: ao tocar um workflow legado, todas as suas
referências externas precisam estar imutáveis antes do merge.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = Path(".github/workflows")
GIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DOCKER_DIGEST_RE = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)['\"]?(?:\s+#.*)?$")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    uses: str
    reason: str


def _run(args: Iterable[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def workflow_paths(root: Path) -> list[str]:
    base = root / WORKFLOW_ROOT
    if not base.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in base.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )


def changed_workflow_paths(root: Path, base_ref: str) -> list[str]:
    result = _run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"origin/{base_ref}...HEAD", "--", str(WORKFLOW_ROOT)],
        cwd=root,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return sorted(
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip().endswith((".yml", ".yaml"))
    )


def parse_uses(path: Path) -> list[tuple[int, str]]:
    refs: list[tuple[int, str]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = USES_RE.match(line)
        if match:
            refs.append((number, match.group(1)))
    return refs


def immutable_reference_error(value: str) -> str | None:
    if value.startswith("./"):
        return None
    if value.startswith("docker://"):
        image = value.removeprefix("docker://")
        if "@" not in image:
            return "docker_image_not_pinned_by_digest"
        digest = image.rsplit("@", 1)[1]
        return None if DOCKER_DIGEST_RE.fullmatch(digest) else "docker_image_not_pinned_by_sha256"
    if "@" not in value:
        return "external_action_missing_ref"
    target, ref = value.rsplit("@", 1)
    if not target or "/" not in target:
        return "external_action_invalid_target"
    if not GIT_SHA_RE.fullmatch(ref):
        return "external_action_ref_is_mutable"
    return None


def scan(root: Path, paths: Iterable[str]) -> list[Finding]:
    findings: list[Finding] = []
    for rel in sorted(set(paths)):
        path = root / rel
        if not path.is_file():
            continue
        for line, value in parse_uses(path):
            reason = immutable_reference_error(value)
            if reason:
                findings.append(Finding(rel, line, value, reason))
    return findings


def build_report(root: Path, base_ref: str, scope: str) -> dict[str, object]:
    all_paths = workflow_paths(root)
    repository_findings = scan(root, all_paths)
    if scope == "all":
        blocking_paths = all_paths
    else:
        blocking_paths = changed_workflow_paths(root, base_ref)
    blocking_findings = scan(root, blocking_paths)
    return {
        "schema_version": "1.0",
        "scope": scope,
        "base_ref": base_ref,
        "workflow_count": len(all_paths),
        "blocking_workflow_count": len(blocking_paths),
        "repository_violation_count": len(repository_findings),
        "blocking_violation_count": len(blocking_findings),
        "blocking_workflows": blocking_paths,
        "blocking_findings": [asdict(item) for item in blocking_findings],
        "repository_findings": [asdict(item) for item in repository_findings],
    }


def self_test_negative() -> bool:
    with tempfile.TemporaryDirectory(prefix="reqsys-action-pin-negative-") as tmp:
        root = Path(tmp)
        workflow = root / WORKFLOW_ROOT / "negative.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(
            "name: negative\non: workflow_dispatch\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v4\n",
            encoding="utf-8",
        )
        findings = scan(root, [workflow.relative_to(root).as_posix()])
        return len(findings) == 1 and findings[0].reason == "external_action_ref_is_mutable"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida imutabilidade das referências uses: em GitHub Actions.")
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--scope", choices=("changed", "all"), default="changed")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/pre-pr-readiness/action-immutability.json"),
    )
    parser.add_argument("--self-test-negative", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test_negative:
        ok = self_test_negative()
        print(json.dumps({"self_test_negative": ok}))
        return 0 if ok else 1

    report = build_report(Path.cwd(), args.base_ref, args.scope)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))

    if report["blocking_violation_count"]:
        for item in report["blocking_findings"]:
            print(
                f"{item['path']}:{item['line']}: {item['reason']}: {item['uses']}",
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
