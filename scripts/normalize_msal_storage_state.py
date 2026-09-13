#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class StorageStateError(RuntimeError):
    pass


def normalize_bundle(payload: Any) -> tuple[dict[str, Any], int]:
    if not isinstance(payload, dict):
        raise StorageStateError("msal_storage_state_envelope_invalido")

    storage = payload.get("sessionStorage")
    if not isinstance(storage, list):
        raise StorageStateError("msal_session_storage_invalido")

    normalized: list[dict[str, Any]] = []
    removed = 0
    for entry in storage:
        if not isinstance(entry, dict):
            removed += 1
            continue

        # Reproduz a coerção do parser legado do E2E para eliminar apenas
        # valores que seriam JSON válido, mas não objetos e portanto quebrariam `.get()`.
        raw = str(entry.get("value") or "")
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            normalized.append(entry)
            continue
        if not isinstance(decoded, dict):
            removed += 1
            continue
        normalized.append(entry)

    result = dict(payload)
    result["sessionStorage"] = normalized
    return result, removed


def normalize_file(path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    normalized, removed = normalize_bundle(payload)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return len(normalized["sessionStorage"]), removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Normaliza storage state MSAL sem imprimir valores sensíveis")
    parser.add_argument("--path", required=True, type=Path)
    args = parser.parse_args()
    try:
        kept, removed = normalize_file(args.path)
    except (OSError, json.JSONDecodeError, StorageStateError) as exc:
        reason = str(exc) if isinstance(exc, StorageStateError) else exc.__class__.__name__
        print(json.dumps({"status": "blocked", "reason": reason}))
        return 4
    print(json.dumps({"status": "normalized", "entries_kept": kept, "entries_removed": removed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
