#!/usr/bin/env python3
"""Probe somente leitura do alvo DEV da Prospecção Movimento."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "scripts" / "sincronizar_movimento_email_corporate.py"
SPEC = importlib.util.spec_from_file_location("movimento_email_corporate", SYNC)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def main() -> int:
    explicit = bridge._explicit_dsn_configured("MOVIMENTO_EMAIL_TARGET_DSN")
    payload = {
        "schema_version": "1.0.0",
        "feature": "movimento_email_target_dev_probe",
        "configuration_mode": "explicit_dsn" if explicit else "integrated_local_default",
        "secret_exposed": False,
        "production_touched": False,
        "objects": {},
        "passed": False,
    }
    conn = bridge.connect(bridge.resolve_target_dsn())
    try:
        database = bridge.assert_target_dev(conn)
        payload["database_hash"] = bridge.sha256_text(database)[:16]
        cur = conn.cursor()
        for name, item in bridge.DEFAULT_MAPPING.items():
            target_type = "U"
            view_type = "V"
            cur.execute("SELECT CASE WHEN OBJECT_ID(?, ?) IS NULL THEN 0 ELSE 1 END", item["target_object"], target_type)
            target_ok = bool(cur.fetchone()[0])
            cur.execute("SELECT CASE WHEN OBJECT_ID(?, ?) IS NULL THEN 0 ELSE 1 END", item["view"], view_type)
            view_ok = bool(cur.fetchone()[0])
            payload["objects"][name] = {"target": target_ok, "view": view_ok}
        payload["passed"] = all(v["target"] and v["view"] for v in payload["objects"].values())
    finally:
        conn.close()

    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
