#!/usr/bin/env python3
"""Encrypt and verify a retirement backup without persisting its key."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

KEY_ENV = "FLY_RETIREMENT_BACKUP_KEY"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cipher() -> Fernet:
    key = os.getenv(KEY_ENV, "").strip()
    if not key:
        raise SystemExit(f"{KEY_ENV} is required")
    return Fernet(key.encode("ascii"))


def encrypt(source: Path, destination: Path) -> dict[str, object]:
    plaintext = source.read_bytes()
    envelope = _cipher().encrypt(plaintext)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(envelope)
    temporary.replace(destination)
    return {
        "source": str(source),
        "destination": str(destination),
        "plaintext_size": len(plaintext),
        "plaintext_sha256": _sha256(plaintext),
        "envelope_size": len(envelope),
        "envelope_sha256": _sha256(envelope),
        "verified": _cipher().decrypt(envelope) == plaintext,
    }


def verify(source: Path, envelope_path: Path) -> dict[str, object]:
    plaintext = source.read_bytes()
    envelope = envelope_path.read_bytes()
    try:
        decrypted = _cipher().decrypt(envelope)
    except InvalidToken as exc:
        raise SystemExit("backup envelope authentication failed") from exc
    return {
        "source": str(source),
        "envelope": str(envelope_path),
        "plaintext_sha256": _sha256(plaintext),
        "decrypted_sha256": _sha256(decrypted),
        "envelope_sha256": _sha256(envelope),
        "verified": decrypted == plaintext,
    }


def decrypt(source: Path, destination: Path) -> dict[str, object]:
    envelope = source.read_bytes()
    try:
        plaintext = _cipher().decrypt(envelope)
    except InvalidToken as exc:
        raise SystemExit("backup envelope authentication failed") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(plaintext)
    temporary.replace(destination)
    return {
        "source": str(source),
        "destination": str(destination),
        "plaintext_size": len(plaintext),
        "plaintext_sha256": _sha256(plaintext),
        "envelope_sha256": _sha256(envelope),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("encrypt", "decrypt"):
        child = subparsers.add_parser(command)
        child.add_argument("source", type=Path)
        child.add_argument("destination", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("source", type=Path)
    verify_parser.add_argument("envelope", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "encrypt":
        result = encrypt(args.source, args.destination)
    elif args.command == "decrypt":
        result = decrypt(args.source, args.destination)
    else:
        result = verify(args.source, args.envelope)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result.get("verified", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
