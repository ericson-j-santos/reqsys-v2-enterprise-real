#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.validate_bacen_idp_mfa_evidence import load_document, validate
except ModuleNotFoundError:  # execução direta a partir de scripts/
    from validate_bacen_idp_mfa_evidence import load_document, validate

HEX = set("0123456789abcdef")


def normalize_sha256(value: str) -> str:
    digest = value.strip().lower()
    if len(digest) != 64 or any(character not in HEX for character in digest):
        raise ValueError("expected_sha256 inválido")
    return digest


def decode_base64_environment(variable_name: str) -> bytes:
    encoded = os.environ.get(variable_name, "").strip()
    if not encoded:
        raise ValueError(f"secret {variable_name} não configurado")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("payload MFA não é base64 válido") from exc
    if not payload:
        raise ValueError("payload MFA vazio")
    return payload


def ingest_payload(
    payload: bytes,
    expected_sha256: str,
    *,
    require_evidenced: bool,
) -> tuple[dict[str, Any], bool]:
    expected = normalize_sha256(expected_sha256)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError("source_sha256_mismatch")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="bacen-02-mfa-", suffix=".json", delete=False) as handle:
            handle.write(payload)
            temporary_path = Path(handle.name)
        temporary_path.chmod(0o600)
        report = validate(load_document(temporary_path), temporary_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    accepted = bool(report["structural_checks_passed"])
    if require_evidenced:
        accepted = accepted and bool(report["mfa_evidenced"])

    report["ingestion"] = {
        "mode": "governed_secret_payload",
        "expected_sha256_match": True,
        "raw_evidence_persisted": False,
        "require_evidenced": require_evidenced,
        "accepted": accepted,
    }
    report["human_review_required"] = not accepted
    return report, accepted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingere evidência MFA externa sem persistir o payload bruto"
    )
    parser.add_argument("--base64-env", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-evidenced", action="store_true")
    args = parser.parse_args()

    try:
        report, accepted = ingest_payload(
            decode_base64_environment(args.base64_env),
            args.expected_sha256,
            require_evidenced=args.require_evidenced,
        )
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"BACEN-02 governed MFA ingestion failed: {type(exc).__name__}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "BACEN-02 governed MFA ingestion completed: "
        f"accepted={str(accepted).lower()}"
    )
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
