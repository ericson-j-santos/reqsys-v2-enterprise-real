#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


class KeyErrorRuntime(RuntimeError):
    pass


def _tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise KeyErrorRuntime(f"tool_missing:{name}")
    return resolved


def _run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "sem detalhe").strip().replace("\n", " ")
        raise KeyErrorRuntime(f"command_failed:{Path(args[0]).name}:exit_{result.returncode}:{detail[:300]}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    openssl = _tool("openssl")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    private_key = output_dir / "private.pem"
    public_key = output_dir / "public.pem"

    if private_key.exists() or public_key.exists():
        raise KeyErrorRuntime("ephemeral_key_material_already_exists")

    _run([openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(private_key)])
    _run([openssl, "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)])

    public_text = public_key.read_text(encoding="utf-8")
    print(json.dumps({
        "status": "ready",
        "private_key_persisted_local_only": True,
        "public_key_pem": public_text,
        "secret_value_exposed": False,
        "production_touched": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
