#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
NGINX_DIR = ROOT / "infra" / "nginx"

required_files = [
    "nginx.conf",
    "conf.d/security-headers.conf",
    "conf.d/cors.conf",
    "conf.d/tls.conf",
    "conf.d/rate-limit.conf",
    "conf.d/upstreams.conf",
]

required_terms = [
    "server_tokens off",
    "ssl_protocols TLSv1.2 TLSv1.3",
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "limit_req_zone",
    "limit_conn_zone",
    "X-Request-ID",
    "X-Correlation-ID",
    "return 308 https://$host$request_uri",
]

forbidden_terms = [
    "Access-Control-Allow-Origin *",
    "ssl_protocols TLSv1 TLSv1.1",
    "server_tokens on",
    "client_max_body_size 0",
]


def main() -> int:
    missing = [name for name in required_files if not (NGINX_DIR / name).exists()]
    if missing:
        print("nginx-security: FALHA")
        print("Arquivos ausentes: " + ", ".join(missing))
        return 1

    content = "\n".join((NGINX_DIR / name).read_text(encoding="utf-8") for name in required_files)
    normalized = " ".join(content.split())
    errors = []

    for term in required_terms:
        if term not in normalized and term not in content:
            errors.append("Obrigatorio ausente: " + term)

    for term in forbidden_terms:
        if term in normalized or term in content:
            errors.append("Padrao proibido encontrado: " + term)

    if errors:
        print("nginx-security: FALHA")
        for error in errors:
            print("- " + error)
        return 1

    print("nginx-security: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
