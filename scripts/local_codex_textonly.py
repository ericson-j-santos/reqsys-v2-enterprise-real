#!/usr/bin/env python3
"""Executor Codex local restrito a geração de texto em workspace ReqSys.

O processo Codex roda com stdin fechado, sandbox read-only e ferramentas de
execução desabilitadas. O chamador continua responsável por Command Gateway,
testes, commit/push e demais gates de governança.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "unified_exec_tty",
    "code_mode_host",
    "apps",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "hooks",
    "plugins",
    "remote_plugin",
    "skill_search",
    "image_generation",
    "multi_agent",
)
SECRET_RE = re.compile(r"(?i)(token|secret|password|passwd|api[_-]?key|authorization)\s*[:=]\s*([^\s]+)")
BEARER_RE = re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+")


def redact(text: str) -> str:
    text = SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return BEARER_RE.sub("Bearer [REDACTED]", text)


def resolve_output(workspace: Path, output_relative: str) -> Path:
    workspace = workspace.resolve()
    output = (workspace / output_relative).resolve()
    if workspace != output and workspace not in output.parents:
        raise ValueError("output fora do workspace")
    return output


def run_codex_textonly(*, codex_bin: Path, workspace: Path, prompt: str, output_relative: str, timeout: int = 240) -> dict[str, object]:
    workspace = workspace.resolve()
    output = resolve_output(workspace, output_relative)
    output.parent.mkdir(parents=True, exist_ok=True)
    args = [str(codex_bin), "exec", "--ephemeral", "--ignore-user-config", "--sandbox", "read-only"]
    for feature in DISABLED_FEATURES:
        args += ["--disable", feature]
    args += ["--output-last-message", str(output), prompt]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=str(workspace),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "result": "CODEX_TEXT_ONLY_TIMEOUT",
            "exit_code": 124,
            "codex_exit_code": None,
            "output_exists": output.is_file(),
            "output_size": output.stat().st_size if output.is_file() else 0,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "stderr_tail": redact((exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else ""),
        }

    output_exists = output.is_file()
    output_size = output.stat().st_size if output_exists else 0
    ok = completed.returncode == 0 and output_exists and output_size > 0
    return {
        "result": "CODEX_TEXT_ONLY_OK" if ok else "CODEX_TEXT_ONLY_FAILED",
        "exit_code": 0 if ok else (completed.returncode or 1),
        "codex_exit_code": completed.returncode,
        "output_exists": output_exists,
        "output_size": output_size,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "stdout_tail": redact(completed.stdout[-2000:]),
        "stderr_tail": redact(completed.stderr[-2000:]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa Codex local em modo text-only/read-only")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True, help="Caminho relativo ao workspace")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--codex-bin", type=Path, default=Path(os.getenv("CODEX_BIN", "codex")))
    parser.add_argument("--timeout", type=int, default=240)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    result = run_codex_textonly(
        codex_bin=ns.codex_bin,
        workspace=ns.workspace,
        prompt=ns.prompt,
        output_relative=ns.output,
        timeout=ns.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
