#!/usr/bin/env python3
"""Captura o JWT admin humano (login real Azure AD) e administra seu vencimento via Cofre.

O JWT expira em ~60min e não dá para "renová-lo" automaticamente sem repetir o
login real (propositalmente — ver discussão sobre não automatizar MFA). O que
este módulo resolve é a fricção de precisar colar o mesmo token fresco em
vários lugares (arquivos .http, terminais, scripts) dentro da mesma janela de
60min: você guarda uma vez (`set` ou `listen`), e qualquer coisa local pode
buscar com `get` até ele expirar.

Fluxo (com captura manual):
  1) Login real em https://reqsys-app-{env}.fly.dev, copiar o JWT do DevTools
     (Application > Local Storage > reqsys_token).
  2) python scripts/cofre_human_token.py bootstrap-reader --environment dev
     (uma vez por ambiente: cria um token de leitura do Cofre restrito à
     chave human_admin_jwt:{env} e grava em .cofre/vault-token-{env}.local,
     fora do git. Pede o JWT admin colado na hora.)
  3) python scripts/cofre_human_token.py set --environment dev
     (grava o JWT recém-obtido no Cofre, com o exp decodificado do próprio
     token. Autentica com o JWT colado.)
  4) python scripts/cofre_human_token.py get --environment dev [--write-http]
     (busca o JWT guardado usando o token de leitura escopado do passo 2 —
     nunca o JWT admin. Se expirado, avisa e pede para repetir o passo 1+3.
     --write-http atualiza @jwt/@jwtStg em scratch-api-calls.http.)

Fluxo (com captura automática do passo 3, via bookmarklet):
  1) Login real em https://reqsys-app-{env}.fly.dev (continua manual, nunca
     automatizado).
  2) python scripts/cofre_human_token.py listen --environment dev
     — imprime um bookmarklet e sobe um listener em 127.0.0.1 (nunca exposto
     na rede), que só aceita POST vindo da origem exata do frontend daquele
     ambiente e desliga sozinho após a primeira captura ou após o timeout.
  3) Salve o texto impresso como favorito do navegador (cole no campo URL do
     favorito) e clique nele com a aba do ReqSys aberta e logada — o JWT vai
     direto do localStorage pro Cofre, sem copiar/colar.

Nada aqui armazena senha ou contorna MFA: o login real continua manual, e o
listener só entende o JWT que o próprio navegador já tinha em memória depois
desse login.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
VAULT_TOKEN_DIR = REPO_ROOT / ".cofre"
HTTP_SCRATCH_FILE = REPO_ROOT / "scratch-api-calls.http"

ENVIRONMENTS = {
    "dev": "https://reqsys-api-dev.fly.dev",
    "stg": "https://reqsys-api-stg.fly.dev",
}

FRONTEND_ORIGINS = {
    "dev": "https://reqsys-app-dev.fly.dev",
    "stg": "https://reqsys-app-stg.fly.dev",
}

HTTP_VAR_BY_ENV = {
    "dev": "jwt",
    "stg": "jwtStg",
}

LISTEN_DEFAULT_PORT = 8765
LISTEN_DEFAULT_TIMEOUT_SECONDS = 180
_MAX_CAPTURE_BODY_BYTES = 8192

_BOOKMARKLET_TEMPLATE = """(function(){
var t=localStorage.getItem('reqsys_token');
if(!t){alert('reqsys_token nao encontrado -- faca login primeiro.');return;}
fetch('http://127.0.0.1:__PORT__/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:t})})
.then(function(r){return r.json();})
.then(function(j){alert(j.ok?('Token capturado no Cofre. Expira em ~'+j.expires_in_min+' min.'):('Falha: '+(j.erro||'?')));})
.catch(function(e){alert('Falha ao conectar no listener local (rode: python scripts/cofre_human_token.py listen): '+e);});
})();"""


class CofreTokenError(Exception):
    """Erro previsto neste módulo — convertido em SystemExit na CLI, em resposta HTTP no listener."""


def _base_url(environment: str, override: str | None) -> str:
    if override:
        return override.rstrip("/")
    if environment not in ENVIRONMENTS:
        raise CofreTokenError(
            f"Ambiente '{environment}' desconhecido. Use --base-url para apontar explicitamente."
        )
    return ENVIRONMENTS[environment]


def _vault_token_path(environment: str) -> Path:
    return VAULT_TOKEN_DIR / f"vault-token-{environment}.local"


def _decode_jwt_exp(token: str) -> int:
    parts = token.split(".")
    if len(parts) != 3:
        raise CofreTokenError("Isso não parece um JWT válido (esperado 3 segmentos separados por '.').")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as exc:
        raise CofreTokenError(f"Falha ao decodificar o payload do JWT: {exc}")
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise CofreTokenError("JWT não tem claim 'exp' numérica.")
    return exp


def _http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: dict | None = None,
) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, data=data, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CofreTokenError(f"HTTP {exc.code} em {method} {url}: {detail}")
    except URLError as exc:
        raise CofreTokenError(f"Falha de rede em {method} {url}: {exc.reason}")


def _set_token(environment: str, base_url_override: str | None, admin_jwt: str) -> int:
    """Grava o JWT no Cofre (chave human_admin_jwt:{environment}). Retorna o exp (epoch)."""
    base_url = _base_url(environment, base_url_override)
    exp = _decode_jwt_exp(admin_jwt)

    value = json.dumps({
        "token": admin_jwt,
        "exp": exp,
        "environment": environment,
        "captured_at": int(time.time()),
    })

    _http_request(
        "POST",
        f"{base_url}/v1/cofre/segredos",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        body={"key": f"human_admin_jwt:{environment}", "value": value},
    )
    return exp


def cmd_bootstrap_reader(args: argparse.Namespace) -> None:
    base_url = _base_url(args.environment, args.base_url)
    admin_jwt = args.token or input("Cole o JWT admin (login real Azure AD): ").strip()
    _decode_jwt_exp(admin_jwt)  # valida formato cedo

    resp = _http_request(
        "POST",
        f"{base_url}/v1/cofre/tokens",
        headers={"Authorization": f"Bearer {admin_jwt}"},
        body={
            "label": f"human-jwt-reader-{args.environment}",
            "key_patterns": [f"human_admin_jwt:{args.environment}"],
        },
    )
    scoped_token = resp["data"]["token"]

    VAULT_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    path = _vault_token_path(args.environment)
    path.write_text(scoped_token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    print(f"Token de leitura escopado criado e salvo em {path} (fora do git).")
    print("Esse token só consegue ler a chave "
          f"'human_admin_jwt:{args.environment}' — guarde-o, não será mostrado de novo pelo Cofre.")


def cmd_set(args: argparse.Namespace) -> None:
    admin_jwt = args.token or input("Cole o JWT admin recém-obtido (login real Azure AD): ").strip()
    exp = _set_token(args.environment, args.base_url, admin_jwt)
    remaining_min = max(0, (exp - int(time.time())) // 60)
    print(f"JWT guardado no Cofre ({args.environment}). Expira em ~{remaining_min}min.")


def cmd_get(args: argparse.Namespace) -> None:
    base_url = _base_url(args.environment, args.base_url)
    reader_path = _vault_token_path(args.environment)
    if not reader_path.exists():
        raise CofreTokenError(
            f"Nenhum token de leitura local para '{args.environment}'. "
            f"Rode primeiro: python scripts/cofre_human_token.py bootstrap-reader --environment {args.environment}"
        )
    vault_token = reader_path.read_text(encoding="utf-8").strip()

    resp = _http_request(
        "GET",
        f"{base_url}/v1/cofre/segredos/human_admin_jwt:{args.environment}",
        headers={"X-Vault-Token": vault_token},
    )
    stored = json.loads(resp["data"]["value"])
    exp = stored["exp"]
    remaining = exp - int(time.time())

    if remaining <= 0:
        raise CofreTokenError(
            f"JWT guardado para '{args.environment}' expirou há {abs(remaining) // 60}min. "
            "Faça login de novo e rode 'set' (ou 'listen')."
        )

    print(f"(válido por mais ~{remaining // 60}min)", file=sys.stderr)

    if args.write_http:
        _write_http_var(args.environment, stored["token"])
        print(f"scratch-api-calls.http atualizado (@{HTTP_VAR_BY_ENV[args.environment]}).", file=sys.stderr)

    print(stored["token"])


def _write_http_var(environment: str, token: str) -> None:
    if not HTTP_SCRATCH_FILE.exists():
        raise CofreTokenError(f"{HTTP_SCRATCH_FILE} não existe.")
    var_name = HTTP_VAR_BY_ENV.get(environment)
    if not var_name:
        raise CofreTokenError(f"Sem variável .http mapeada para o ambiente '{environment}'.")
    text = HTTP_SCRATCH_FILE.read_text(encoding="utf-8")
    pattern = re.compile(rf"^@{re.escape(var_name)} =.*$", re.MULTILINE)
    new_text, count = pattern.subn(f"@{var_name} = {token}", text, count=1)
    if count == 0:
        raise CofreTokenError(f"Linha '@{var_name} = ...' não encontrada em {HTTP_SCRATCH_FILE}.")
    HTTP_SCRATCH_FILE.write_text(new_text, encoding="utf-8")


def _build_bookmarklet(port: int) -> str:
    js = _BOOKMARKLET_TEMPLATE.replace("__PORT__", str(port))
    js_one_line = " ".join(js.split())
    return "javascript:" + js_one_line


def _make_capture_handler(environment: str, base_url_override: str | None, allowed_origin: str, result: dict):
    class _CaptureHandler(BaseHTTPRequestHandler):
        server_version = "ReqSysCofreCapture/1.0"

        def log_message(self, format, *args):  # noqa: A002 - assinatura fixa do BaseHTTPRequestHandler
            pass  # silencia log padrão (evita ecoar Origin/IP no terminal)

        def _cors_headers(self) -> None:
            origin = self.headers.get("Origin", "")
            if origin and origin == allowed_origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _reply_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802 - nome exigido pelo BaseHTTPRequestHandler
            self.send_response(204)
            self._cors_headers()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            # Visitar a URL direto no navegador (em vez de clicar no bookmarklet) cai
            # aqui — sem isso o BaseHTTPRequestHandler devolveria um 501 cru e confuso.
            self._reply_json(200, {
                "ok": True,
                "listener": "ativo",
                "mensagem": (
                    "Este listener só aceita POST vindo do bookmarklet (fetch), não visita direta. "
                    "Clique no favorito criado por 'listen' com a aba do ReqSys logada."
                ),
            })

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/capture":
                self._reply_json(404, {"ok": False, "erro": "rota desconhecida"})
                return

            origin = self.headers.get("Origin", "")
            if origin != allowed_origin:
                self._reply_json(403, {"ok": False, "erro": "origem não permitida"})
                return

            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > _MAX_CAPTURE_BODY_BYTES:
                    raise CofreTokenError("corpo da requisição ausente ou grande demais")
                payload = json.loads(self.rfile.read(length))
                token = (payload.get("token") or "").strip()
                if not token:
                    raise CofreTokenError("campo 'token' vazio")

                exp = _set_token(environment, base_url_override, token)
                remaining_min = max(0, (exp - int(time.time())) // 60)

                result["done"] = True
                result["ok"] = True
                result["expires_in_min"] = remaining_min
                self._reply_json(200, {"ok": True, "expires_in_min": remaining_min})
            except CofreTokenError as exc:
                result["done"] = True
                result["ok"] = False
                result["erro"] = str(exc)
                self._reply_json(400, {"ok": False, "erro": str(exc)})
            except Exception as exc:
                result["done"] = True
                result["ok"] = False
                result["erro"] = str(exc)
                self._reply_json(500, {"ok": False, "erro": str(exc)})

    return _CaptureHandler


def cmd_listen(args: argparse.Namespace) -> None:
    _base_url(args.environment, args.base_url)  # valida ambiente/--base-url cedo
    allowed_origin = FRONTEND_ORIGINS.get(args.environment)
    if not allowed_origin:
        raise CofreTokenError(f"Sem origem de frontend mapeada para '{args.environment}'.")

    print("Cole este bookmarklet como URL de um novo favorito no navegador:\n")
    print(_build_bookmarklet(args.port))
    print(f"\nCom {allowed_origin} aberto e logado (login real Azure AD), clique no favorito.")
    print(f"Escutando em http://127.0.0.1:{args.port}/capture — timeout em {args.timeout_seconds}s, "
          "aceita só a origem do frontend acima, desliga sozinho após a 1a captura.\n")

    result = {"done": False, "ok": False, "erro": None, "expires_in_min": None}
    handler_cls = _make_capture_handler(args.environment, args.base_url, allowed_origin, result)
    server = HTTPServer(("127.0.0.1", args.port), handler_cls)
    server.timeout = 1.0

    deadline = time.time() + args.timeout_seconds
    try:
        while time.time() < deadline and not result["done"]:
            server.handle_request()
    finally:
        server.server_close()

    if not result["done"]:
        raise CofreTokenError("Tempo esgotado sem captura. Rode de novo e clique no bookmarklet mais rápido.")
    if not result["ok"]:
        raise CofreTokenError(f"Captura falhou: {result['erro']}")

    print(f"JWT capturado e guardado no Cofre ({args.environment}). Expira em ~{result['expires_in_min']}min.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--environment", required=True, choices=sorted(ENVIRONMENTS))
    common.add_argument("--base-url", default=None, help="Sobrescreve a URL base padrão do ambiente.")

    p_bootstrap = sub.add_parser("bootstrap-reader", parents=[common], help="Cria o token de leitura escopado (uma vez por ambiente).")
    p_bootstrap.add_argument("--token", default=None, help="JWT admin (se omitido, pede via input()).")
    p_bootstrap.set_defaults(func=cmd_bootstrap_reader)

    p_set = sub.add_parser("set", parents=[common], help="Guarda o JWT admin recém-obtido no Cofre (captura manual).")
    p_set.add_argument("--token", default=None, help="JWT admin (se omitido, pede via input()).")
    p_set.set_defaults(func=cmd_set)

    p_get = sub.add_parser("get", parents=[common], help="Busca o JWT guardado, se ainda válido.")
    p_get.add_argument("--write-http", action="store_true", help="Atualiza @jwt/@jwtStg em scratch-api-calls.http.")
    p_get.set_defaults(func=cmd_get)

    p_listen = sub.add_parser(
        "listen", parents=[common],
        help="Sobe um listener local (127.0.0.1) que captura o JWT via bookmarklet, sem copiar/colar.",
    )
    p_listen.add_argument("--port", type=int, default=LISTEN_DEFAULT_PORT)
    p_listen.add_argument("--timeout-seconds", type=int, default=LISTEN_DEFAULT_TIMEOUT_SECONDS)
    p_listen.set_defaults(func=cmd_listen)

    args = parser.parse_args()
    try:
        args.func(args)
    except CofreTokenError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
