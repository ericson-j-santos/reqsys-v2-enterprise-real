#!/usr/bin/env python3
"""
Cofre de segredos local, standalone e isolado (AES-256-GCM + keyring do SO).

Nao depende do backend do ReqSys, de FastAPI, banco de dados ou rede - funciona
sozinho em qualquer computador com Python 3.9+ e as libs `keyring` e
`cryptography` instaladas.

Cada maquina tem seu proprio armazenamento (Credential Manager no Windows,
Secret Service no Linux, Keychain no macOS): copiar este arquivo para outro
computador NAO copia os segredos - cria um cofre novo, isolado, la.

Uso:
  pip install keyring cryptography
  python cofre_vault_standalone.py init
  python cofre_vault_standalone.py set JWT_SECRET "valor-forte-min-32-chars"
  python cofre_vault_standalone.py get JWT_SECRET
  python cofre_vault_standalone.py delete JWT_SECRET
  python cofre_vault_standalone.py list
  python cofre_vault_standalone.py status
  python cofre_vault_standalone.py dashboard [saida.html]
  python cofre_vault_standalone.py import-env [caminho/.env]
  python cofre_vault_standalone.py gen-token

Variavel de ambiente opcional:
  REQSYS_VAULT_SERVICE_NAME  nome do "service" no keyring (default: mvp-intelligence-vault)
"""
from __future__ import annotations

import argparse
import base64 as _b64
import html as _html
import json as _json
import os
import secrets as _secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import keyring
except ImportError:
    print("[ERRO] Dependencia ausente: pip install keyring", file=sys.stderr)
    sys.exit(1)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("[ERRO] Dependencia ausente: pip install cryptography", file=sys.stderr)
    sys.exit(1)

_DEFAULT_SERVICE = "mvp-intelligence-vault"
_MASTER_KEY_SLOT = "__master_key__"
_INDEX_SLOT = "__index__"
_RESERVED_SLOTS = {_MASTER_KEY_SLOT, _INDEX_SLOT}
_NONCE_BYTES = 12


def _service_name() -> str:
    return os.getenv("REQSYS_VAULT_SERVICE_NAME", _DEFAULT_SERVICE).strip() or _DEFAULT_SERVICE


def _read_index(service: str) -> list[str]:
    try:
        raw = keyring.get_password(service, _INDEX_SLOT)
        if not raw:
            return []
        data = _json.loads(raw)
        return [str(k) for k in data] if isinstance(data, list) else []
    except Exception:
        return []


def _write_index(service: str, keys: list[str]) -> None:
    keyring.set_password(service, _INDEX_SLOT, _json.dumps(sorted(set(keys))))


def list_secrets(service: str | None = None) -> list[str]:
    """Nomes dos segredos gravados (nunca os valores)."""
    service = service or _service_name()
    return _read_index(service)


def vault_initialized(service: str | None = None) -> bool:
    service = service or _service_name()
    try:
        return bool(keyring.get_password(service, _MASTER_KEY_SLOT))
    except Exception:
        return False


def init_vault(service: str | None = None, overwrite: bool = False) -> bool:
    service = service or _service_name()
    existing = keyring.get_password(service, _MASTER_KEY_SLOT)
    if existing and not overwrite:
        return False
    master_key = _secrets.token_bytes(32)
    keyring.set_password(service, _MASTER_KEY_SLOT, _b64.b64encode(master_key).decode())
    return True


def write_secret(key: str, value: str, service: str | None = None) -> None:
    if not key or not key.strip():
        raise ValueError("Chave nao pode ser vazia")
    if key in _RESERVED_SLOTS:
        raise ValueError(f'Chave reservada "{key}" nao pode ser usada para segredos')
    service = service or _service_name()
    raw_master = keyring.get_password(service, _MASTER_KEY_SLOT)
    if not raw_master:
        raise RuntimeError('Vault nao inicializado. Rode "init" primeiro')
    master_key = _b64.b64decode(raw_master)
    nonce = _secrets.token_bytes(_NONCE_BYTES)
    ciphertext = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    blob = _b64.b64encode(nonce + ciphertext).decode()
    keyring.set_password(service, key, blob)
    index = _read_index(service)
    if key not in index:
        index.append(key)
        _write_index(service, index)


def read_secret(key: str, service: str | None = None) -> str | None:
    service = service or _service_name()
    try:
        raw_master = keyring.get_password(service, _MASTER_KEY_SLOT)
        if not raw_master:
            return None
        blob = keyring.get_password(service, key)
        if blob is None:
            return None
        master_key = _b64.b64decode(raw_master)
        raw = _b64.b64decode(blob)
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return AESGCM(master_key).decrypt(nonce, ciphertext, None).decode()
    except Exception:
        return None


def delete_secret(key: str, service: str | None = None) -> bool:
    service = service or _service_name()
    try:
        existing = keyring.get_password(service, key)
        if existing is None:
            return False
        keyring.delete_password(service, key)
        if key not in _RESERVED_SLOTS:
            index = _read_index(service)
            if key in index:
                index.remove(key)
                _write_index(service, index)
        return True
    except Exception:
        return False


def _build_dashboard_html(service: str, initialized: bool, keys: list[str]) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    status_label = "INICIALIZADO" if initialized else "NAO INICIALIZADO"
    status_color = "#16a34a" if initialized else "#dc2626"
    rows = "".join(
        f"<tr><td>{_html.escape(k)}</td><td class='oculto'>········</td></tr>" for k in keys
    ) or "<tr><td colspan='2' class='vazio'>Nenhum segredo gravado.</td></tr>"

    return f"""<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Cofre Standalone - Dashboard</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 2rem;
          background: #0b0f14; color: #e5e7eb; }}
  @media (prefers-color-scheme: light) {{
    body {{ background: #f8fafc; color: #0f172a; }}
  }}
  .card {{ max-width: 720px; margin: 0 auto; background: rgba(127,127,127,0.08);
           border: 1px solid rgba(127,127,127,0.2); border-radius: 12px; padding: 1.5rem 2rem; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 .25rem; }}
  .sub {{ opacity: .65; font-size: .85rem; margin-bottom: 1.25rem; }}
  .badge {{ display: inline-block; padding: .25rem .75rem; border-radius: 999px;
            font-weight: 600; font-size: .8rem; color: white; background: {status_color}; }}
  .stats {{ display: flex; gap: 1rem; margin: 1.25rem 0; }}
  .stat {{ flex: 1; text-align: center; padding: .75rem; border-radius: 8px;
           background: rgba(127,127,127,0.08); }}
  .stat b {{ display: block; font-size: 1.5rem; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: .5rem; }}
  td {{ padding: .5rem .25rem; border-bottom: 1px solid rgba(127,127,127,0.15); font-size: .9rem; }}
  .oculto {{ opacity: .5; text-align: right; letter-spacing: 2px; }}
  .vazio {{ text-align: center; opacity: .6; padding: 1rem; }}
  footer {{ margin-top: 1.5rem; font-size: .75rem; opacity: .55; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Cofre Standalone - {_html.escape(service)}</h1>
    <div class="sub">Gerado localmente em {generated_at} - nenhum valor de segredo e exibido nesta pagina.</div>
    <span class="badge">{status_label}</span>
    <div class="stats">
      <div class="stat"><b>{len(keys)}</b>segredo(s) gravado(s)</div>
    </div>
    <table>
      <thead><tr><td><b>Chave</b></td><td><b>Valor</b></td></tr></thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    <footer>cofre_vault_standalone.py &mdash; AES-256-GCM + keyring do SO &mdash; 100% offline, sem CDN externo.</footer>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_init(args):
    service = _service_name()
    if vault_initialized() and not args.force:
        print(f'[OK] Vault "{service}" ja esta inicializado.')
        print('     Use --force para recriar a master key (invalida segredos existentes).')
        return
    if init_vault(overwrite=args.force):
        print(f'[OK] Vault "{service}" inicializado com nova master key.')
    else:
        print("[ERRO] Nao foi possivel inicializar o vault.")
        sys.exit(1)


def cmd_set(args):
    try:
        write_secret(args.key, args.value)
        print(f'[OK] Segredo "{args.key}" gravado no vault.')
    except (RuntimeError, ValueError) as exc:
        print(f"[ERRO] {exc}")
        sys.exit(1)


def cmd_get(args):
    value = read_secret(args.key)
    if value is None:
        print(f'[ERRO] Segredo "{args.key}" nao encontrado ou vault nao inicializado.', file=sys.stderr)
        sys.exit(1)
    print(value)


def cmd_delete(args):
    if delete_secret(args.key):
        print(f'[OK] Segredo "{args.key}" removido.')
    else:
        print(f'[AVISO] Segredo "{args.key}" nao encontrado.')


def cmd_list(_args):
    service = _service_name()
    if not vault_initialized():
        print("[AVISO] Vault nao inicializado.")
        return
    keys = list_secrets(service)
    if not keys:
        print("  Nenhum segredo gravado.")
        return
    print(f"  {len(keys)} segredo(s):")
    for k in keys:
        print(f"    - {k}")


def cmd_status(_args):
    service = _service_name()
    initialized = vault_initialized()
    print(f"Service : {service}")
    print(f'Estado  : {"INICIALIZADO" if initialized else "NAO INICIALIZADO"}')
    if initialized:
        print(f"Segredos: {len(list_secrets(service))}")


def cmd_dashboard(args):
    service = _service_name()
    initialized = vault_initialized()
    keys = list_secrets(service) if initialized else []
    destino = Path(args.output)
    destino.write_text(_build_dashboard_html(service, initialized, keys), encoding="utf-8")
    print(f'[OK] Dashboard gerado em "{destino}" ({len(keys)} segredo(s) listado(s), nenhum valor exposto).')


def cmd_import_env(args):
    env_path = Path(args.path)
    if not env_path.exists():
        print(f"[ERRO] {env_path} nao encontrado.")
        sys.exit(1)
    skip = {"REQSYS_VAULT_SERVICE_NAME", "VAULT_API_TOKEN"}
    imported = 0
    with open(env_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key in skip or not val:
                continue
            try:
                write_secret(key, val)
                print(f"  [OK] {key}")
                imported += 1
            except (RuntimeError, ValueError) as exc:
                print(f"  [ERRO] {key}: {exc}")
    print(f"\n{imported} segredo(s) importado(s).")


def cmd_gen_token(_args):
    print(f"VAULT_API_TOKEN={_secrets.token_urlsafe(32)}")


def main():
    parser = argparse.ArgumentParser(description="Cofre de segredos local standalone")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("set")
    p.add_argument("key")
    p.add_argument("value")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("get")
    p.add_argument("key")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("delete")
    p.add_argument("key")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("list")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("status")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("dashboard")
    p.add_argument("output", nargs="?", default="dashboard.html")
    p.set_defaults(func=cmd_dashboard)

    p = sub.add_parser("import-env")
    p.add_argument("path", nargs="?", default=".env")
    p.set_defaults(func=cmd_import_env)

    p = sub.add_parser("gen-token")
    p.set_defaults(func=cmd_gen_token)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
