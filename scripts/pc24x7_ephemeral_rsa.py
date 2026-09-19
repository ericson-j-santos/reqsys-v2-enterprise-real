#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


class KeyErrorRuntime(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError as exc:
        raise KeyErrorRuntime("python_cryptography_missing") from exc

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    private_key = output_dir / "private.pem"
    public_key = output_dir / "public.pem"

    if private_key.exists() or public_key.exists():
        raise KeyErrorRuntime("ephemeral_key_material_already_exists")

    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    private_key.write_bytes(private_bytes)
    public_key.write_bytes(public_bytes)

    print(json.dumps({
        "status": "ready",
        "private_key_persisted_local_only": True,
        "public_key_pem": public_bytes.decode("ascii"),
        "secret_value_exposed": False,
        "production_touched": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
