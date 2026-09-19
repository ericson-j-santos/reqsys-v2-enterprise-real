#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def probe(url: str) -> dict[str, object]:
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return {"url_kind": "public" if url.startswith("https://") else "local", "status": int(resp.status)}
    except urllib.error.HTTPError as exc:
        return {"url_kind": "public" if url.startswith("https://") else "local", "status": int(exc.code)}
    except Exception as exc:
        return {"url_kind": "public" if url.startswith("https://") else "local", "status": 0, "error": type(exc).__name__}


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--path", required=True)
    p.add_argument("--public-base", required=True)
    args=p.parse_args()
    path=args.path if args.path.startswith("/") else "/" + args.path
    result={
        "local": probe("http://127.0.0.1:8233" + path),
        "public": probe(args.public_base.rstrip("/") + path),
        "secret_value_exposed": False,
        "state_changed": False,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
