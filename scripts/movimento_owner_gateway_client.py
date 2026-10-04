#!/usr/bin/env python3
"""Cliente do Owner Data Gateway com nome lógico estável."""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_LOGICAL_NAME = "reqsys-owner-data-gateway"


def load_endpoint(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"logical_name", "host", "port", "token_file"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise RuntimeError("owner_gateway_endpoint_invalid")
    if payload["logical_name"] != DEFAULT_LOGICAL_NAME:
        raise RuntimeError("owner_gateway_logical_name_mismatch")
    return payload


def _request(endpoint: dict, method: str, route: str, payload: dict | None = None) -> dict:
    token = Path(endpoint["token_file"]).read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise RuntimeError("owner_gateway_token_invalid")
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://{endpoint['host']}:{int(endpoint['port'])}{route}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"owner_gateway_http_{exc.code}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("status", "ingest", "sync"))
    parser.add_argument("--endpoint", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--data-referencia")
    args = parser.parse_args()
    endpoint = load_endpoint(args.endpoint)

    if args.command == "status":
        result = _request(endpoint, "GET", "/status")
    elif args.command == "ingest":
        if not args.input:
            raise SystemExit("--input_required")
        result = _request(endpoint, "POST", "/ingest", json.loads(args.input.read_text(encoding="utf-8")))
    else:
        if not args.data_referencia:
            raise SystemExit("--data-referencia_required")
        result = _request(endpoint, "POST", "/sync", {"data_referencia": args.data_referencia})

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status") in {"passed", "applied", "noop"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
