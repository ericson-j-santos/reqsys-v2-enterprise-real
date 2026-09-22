#!/usr/bin/env python3
"""Valida se o bundle publicado do frontend usa origem publica como redirect URI.

O erro AADSTS50011 ocorre quando o bundle antigo envia
`/auth/callback.html` em vez da origem registrada no Microsoft Entra ID.

Uso local apos build:
    cd frontend && npm run build
    python scripts/validar_frontend_auth_redirect.py --dist-dir frontend/dist

Uso contra ambiente publicado:
    python scripts/validar_frontend_auth_redirect.py \
        --frontend-url https://reqsys-app-stg.fly.dev
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FORBIDDEN_PATTERNS = (
    re.compile(r'["\']/?auth/callback\.html["\']'),
    re.compile(r'CALLBACK_PATH\s*=\s*["\']/auth/callback\.html["\']'),
    re.compile(r'vJ\s*=\s*["\']/auth/callback\.html["\']'),
)


def _scan_text(content: str, source: str) -> list[str]:
    errors: list[str] = []
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(content):
            errors.append(f"{source}: padrao proibido {pattern.pattern!r}")
    return errors


def _collect_js_files(dist_dir: Path) -> list[Path]:
    return sorted(dist_dir.glob("assets/*.js"))


def validate_dist(dist_dir: Path) -> dict[str, Any]:
    if not dist_dir.is_dir():
        raise FileNotFoundError(f"Diretorio de build nao encontrado: {dist_dir}")

    js_files = _collect_js_files(dist_dir)
    if not js_files:
        raise FileNotFoundError(f"Nenhum bundle JS encontrado em {dist_dir / 'assets'}")

    errors: list[str] = []
    scanned: list[str] = []
    for js_file in js_files:
        content = js_file.read_text(encoding="utf-8", errors="ignore")
        scanned.append(str(js_file))
        errors.extend(_scan_text(content, str(js_file)))

    return {
        "mode": "dist",
        "dist_dir": str(dist_dir),
        "scanned_files": scanned,
        "success": not errors,
        "errors": errors,
    }


def _fetch(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return response.read().decode("utf-8", errors="ignore")


def validate_public_frontend(frontend_url: str) -> dict[str, Any]:
    base = frontend_url.rstrip("/")
    try:
        index_html = _fetch(base + "/")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha ao buscar frontend em {base}: {exc.reason}") from exc

    script_paths = re.findall(r'<script[^>]+src="([^"]+)"', index_html)
    if not script_paths:
        raise RuntimeError(f"Nenhum script encontrado em {base}")

    errors: list[str] = []
    scanned: list[str] = []
    for script_path in script_paths:
        if not script_path.endswith(".js"):
            continue
        asset_url = script_path if script_path.startswith("http") else f"{base}{script_path}"
        try:
            content = _fetch(asset_url)
        except urllib.error.URLError as exc:
            errors.append(f"{asset_url}: falha ao baixar bundle ({exc.reason})")
            continue
        scanned.append(asset_url)
        errors.extend(_scan_text(content, asset_url))

    return {
        "mode": "public",
        "frontend_url": base,
        "scanned_files": scanned,
        "success": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida redirect URI do bundle frontend ReqSys")
    parser.add_argument("--dist-dir", help="Diretorio dist local, ex.: frontend/dist")
    parser.add_argument("--frontend-url", help="URL publica do frontend, ex.: https://reqsys-app-stg.fly.dev")
    args = parser.parse_args()

    if not args.dist_dir and not args.frontend_url:
        parser.error("Informe --dist-dir ou --frontend-url")

    if args.dist_dir:
        result = validate_dist(Path(args.dist_dir))
    else:
        result = validate_public_frontend(args.frontend_url)

    payload = {
        "validated_at": datetime.now(UTC).isoformat(),
        **result,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
