from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_gitlab_mirror.py"
SPEC = importlib.util.spec_from_file_location("sync_gitlab_mirror_e2e", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def git(cwd: Path | None, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, timeout=30, check=False)
    if p.returncode:
        raise AssertionError(f"git {args[0]} failed: {p.stderr.strip()}")
    return p.stdout.strip()


class SyncGitlabMirrorE2ETest(unittest.TestCase):
    """Repos descartáveis: nenhum GitHub/GitLab real é acessado."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="mirror-git-e2e-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.source = root / "source"
        self.target = root / "destination.git"
        self.evidence = root / "evidence.json"
        git(None, "init", "--bare", "--initial-branch=main", str(self.target))
        git(None, "init", "--initial-branch=main", str(self.source))
        git(self.source, "config", "user.name", "Test")
        git(self.source, "config", "user.email", "test@example.invalid")
        git(self.source, "remote", "add", "target", str(self.target))
        self.commit("initial.txt", "A")
        git(self.source, "push", "target", "main")

    def commit(self, path: str, data: str) -> str:
        (self.source / path).write_text(data, encoding="utf-8")
        git(self.source, "add", path)
        git(self.source, "commit", "-m", path)
        return git(self.source, "rev-parse", "HEAD")

    def remote_sha(self) -> str:
        return git(self.target, "rev-parse", "refs/heads/main")

    def diverge(self) -> tuple[str, str]:
        base = git(self.source, "rev-parse", "HEAD")
        source_sha = self.commit("github-only.txt", "B")
        git(self.source, "switch", "-c", "gitlab-only", base)
        target_sha = self.commit("gitlab-only.txt", "C")
        git(self.source, "push", "target", "HEAD:main")
        git(self.source, "switch", "main")
        return source_sha, target_sha

    def run_mirror(self, *flags: str) -> tuple[int, dict, list]:
        old_cwd = Path.cwd()
        original = MODULE.run_git
        attempts = []

        def inspect_git(args, **kwargs):
            if args[0] == "push":
                attempts.append(tuple(args))
            return original(args, **kwargs)

        argv = ["mirror.py", "--gitlab-repository", str(self.target),
                "--source-ref", "main", "--evidence", str(self.evidence), *flags]
        try:
            os.chdir(self.source)
            with (patch.dict(os.environ, {"GITLAB_MIRROR_TOKEN": "local-test"}),
                  patch.object(sys, "argv", argv),
                  patch.object(MODULE, "run_git", side_effect=inspect_git),
                  contextlib.redirect_stdout(io.StringIO())):
                code = MODULE.main()
        finally:
            os.chdir(old_cwd)
        self.assertTrue(self.evidence.is_file())
        return code, json.loads(self.evidence.read_text(encoding="utf-8")), attempts

    def test_divergence_blocks_before_push_and_replay_is_idempotent(self) -> None:
        source, target = self.diverge()
        for _ in range(2):
            code, e, pushes = self.run_mirror()
            self.assertEqual((code, e["status"], e["action"]), (2, "blocked", "none"))
            self.assertEqual((e["source_sha"], e["target_sha_before"],
                              e["target_sha_after"]), (source, target, target))
            self.assertEqual(pushes, [])
            self.assertEqual(self.remote_sha(), target)

    def test_divergence_is_blocked_even_in_dry_run(self) -> None:
        _, target = self.diverge()
        code, e, pushes = self.run_mirror("--dry-run")
        self.assertEqual((code, e["status"], pushes), (2, "blocked", []))
        self.assertEqual(self.remote_sha(), target)

    def test_in_sync_is_noop(self) -> None:
        before = self.remote_sha()
        code, e, pushes = self.run_mirror()
        self.assertEqual((code, e["action"], pushes), (0, "noop", []))
        self.assertEqual(self.remote_sha(), before)

    def test_fast_forward_then_replay_noop(self) -> None:
        previous = self.remote_sha()
        updated = self.commit("new.txt", "B")
        code, e, pushes = self.run_mirror()
        self.assertEqual((code, e["action"], len(pushes)), (0, "fast_forward", 1))
        self.assertEqual((e["target_sha_before"], e["target_sha_after"]), (previous, updated))
        self.assertEqual(self.remote_sha(), updated)
        code, e, pushes = self.run_mirror()
        self.assertEqual((code, e["action"], pushes), (0, "noop", []))
        self.assertEqual(self.remote_sha(), updated)

    def test_dry_run_never_pushes(self) -> None:
        previous = self.remote_sha()
        self.commit("new.txt", "B")
        code, e, pushes = self.run_mirror("--dry-run")
        self.assertEqual((code, e["action"], pushes), (0, "would_fast_forward", []))
        self.assertEqual(self.remote_sha(), previous)


if __name__ == "__main__":
    unittest.main()
