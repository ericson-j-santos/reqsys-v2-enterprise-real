#!/usr/bin/env python3
"""E2E real do agente local do Noteri: NORMAL -> ESTUDO -> NORMAL."""
from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

AGENT_URL = "http://127.0.0.1:8765"


def request(path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        AGENT_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError(f"resposta inválida do agente: {payload}")
    return payload


def set_and_verify(profile: str, correlation_id: str) -> dict[str, Any]:
    changed = request(
        "/v1/profile",
        method="POST",
        body={"host": "Noteri", "profile": profile, "correlation_id": correlation_id},
    )
    observed = request("/v1/profile")
    expected_acceptance = profile == "NORMAL"
    if observed.get("profile") != profile:
        raise RuntimeError(f"readback divergente: esperado {profile}, obtido {observed.get('profile')}")
    if observed.get("accepts_new_development") is not expected_acceptance:
        raise RuntimeError("accepts_new_development divergente")
    return {"changed": changed, "observed": observed}


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E real NORMAL/ESTUDO do Noteri")
    parser.add_argument("--correlation-prefix", default="noteri-study-live")
    args = parser.parse_args()
    if socket.gethostname().casefold() != "noteri":
        print(json.dumps({"ok": False, "error": "E2E deve rodar no host Noteri"}, ensure_ascii=False))
        return 2

    stamp = str(int(time.time()))
    prefix = f"{args.correlation_prefix}-{stamp}"
    evidence: dict[str, Any] = {"host": socket.gethostname(), "initial": None, "study": None, "normal": None}
    try:
        evidence["initial"] = request("/v1/profile")
        if evidence["initial"].get("profile") != "NORMAL":
            set_and_verify("NORMAL", prefix + "-pre-normal")
        evidence["study"] = set_and_verify("ESTUDO", prefix + "-estudo")
        evidence["normal"] = set_and_verify("NORMAL", prefix + "-normal")
        print(json.dumps({"ok": True, "result": "NOTERI_STUDY_E2E_OK", **evidence}, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, RuntimeError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), **evidence}, ensure_ascii=False, sort_keys=True))
        return 1
    finally:
        try:
            set_and_verify("NORMAL", prefix + "-finally-normal")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
