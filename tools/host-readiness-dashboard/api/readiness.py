"""API de evidências ReqSys: leitura somente, local e fail-closed (sem Docker)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import sys
from urllib.parse import parse_qs, urlsplit

HOSTS = {"desktop": "DESKTOP-PDQK954", "lenovo": "DESKTOP-RP23OGS", "noteri": "Noteri"}
GATES = ("identity", "normal", "sha", "session", "validated", "gateway", "worktree", "lease", "native", "cost", "readback")
CATEGORIES = ("runner", "admissao", "dependencia", "configuracao", "continuidade")
SHA40 = lambda x: isinstance(x, str) and len(x) == 40 and all(c in "0123456789abcdefABCDEF" for c in x)
SHA64 = lambda x: isinstance(x, str) and len(x) == 64 and all(c in "0123456789abcdefABCDEF" for c in x)
MAX_AGE_SECONDS = 300


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def observe_time(value):
    if not isinstance(value, str):
        raise ValueError("observed_at_invalid")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at_invalid") from exc
    if dt.tzinfo is None:
        raise ValueError("observed_at_timezone_missing")
    return dt.astimezone(timezone.utc)


def verify_receipt(receipt, key, rules_sha, now=None):
    """Importar somente recibo assinado por validador independente autorizado."""
    if not isinstance(receipt, dict) or not key or not SHA40(rules_sha):
        raise ValueError("invalid_trust_configuration")
    signature = receipt.get("signature")
    message = {k: v for k, v in receipt.items() if k != "signature"}
    expected = hmac.new(key.encode(), canonical(message).encode(), hashlib.sha256).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        raise ValueError("invalid_signature")
    host = message.get("host_id")
    if message.get("schema_version") != "1" or host not in HOSTS:
        raise ValueError("invalid_schema_or_host")
    if message.get("physical_id") != HOSTS[host]:
        raise ValueError("host_identity_mismatch")
    if message.get("profile") != "NORMAL" or message.get("rules_sha") != rules_sha:
        raise ValueError("profile_or_rules_mismatch")
    if not SHA40(message.get("source_sha")) or not isinstance(message.get("event_id"), str) or not (8 <= len(message["event_id"]) <= 128):
        raise ValueError("invalid_source_or_event")
    if message.get("source") != "github_api_and_gateway_receipt":
        raise ValueError("untrusted_source")
    gates = message.get("gates")
    if not isinstance(gates, dict) or set(gates) != set(GATES) or any(type(gates[k]) is not bool for k in GATES):
        raise ValueError("gates_invalid")
    proof = message.get("independent_readback")
    if not isinstance(proof, dict) or proof.get("verified") is not True or not SHA64(proof.get("artifact_sha256")) or proof.get("artifact_sha256") != proof.get("readback_sha256"):
        raise ValueError("independent_readback_missing")
    runner = message.get("runner")
    if not isinstance(runner, dict) or not isinstance(runner.get("name"), str) or not isinstance(runner.get("version"), str) or not isinstance(runner.get("labels"), list) or "self-hosted" not in runner["labels"]:
        raise ValueError("runner_invalid")
    if message.get("cost_guard") != "COST_ZERO_CONFIRMED" or not isinstance(message.get("cost_evidence"), str) or not message["cost_evidence"].strip():
        raise ValueError("cost_not_verified")
    if message.get("block") not in CATEGORIES or not isinstance(message.get("next_action"), str) or not message["next_action"].strip():
        raise ValueError("classification_missing")
    if type(message.get("requires_human")) is not bool:
        raise ValueError("human_flag_missing")
    checked = observe_time(message.get("observed_at"))
    current = now or datetime.now(timezone.utc)
    age = (current - checked).total_seconds()
    if age < -5 or age > MAX_AGE_SECONDS:
        raise ValueError("observation_expired_or_future")
    return message


def ingest(db_path, receipt, key, rules_sha, now=None):
    message = verify_receipt(receipt, key, rules_sha, now=now)
    encoded = canonical(receipt)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError("database_path_must_be_absolute")
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS evidence (event_id TEXT PRIMARY KEY, host_id TEXT NOT NULL, observed_at TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL)")
        old = db.execute("SELECT digest FROM evidence WHERE event_id=?", (message["event_id"],)).fetchone()
        if old and old[0] != digest:
            raise ValueError("event_id_conflict")
        if not old:
            db.execute("INSERT INTO evidence VALUES (?,?,?,?,?)", (message["event_id"], message["host_id"], message["observed_at"], digest, encoded))
    # Readback do armazenamento; NÃO equivale ao readback físico do host.
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        saved = db.execute("SELECT digest,payload FROM evidence WHERE event_id=?", (message["event_id"],)).fetchone()
    if not saved or saved[0] != digest or hashlib.sha256(saved[1].encode()).hexdigest() != digest:
        raise RuntimeError("storage_readback_failed")
    return {"event_id": message["event_id"], "storage_digest": digest, "storage_readback_verified": True, "replayed": bool(old)}


def snapshots(db_path, key, rules_sha, now=None):
    """Histórico append-only relido; banco ausente bloqueia sem criar arquivo."""
    path = Path(db_path)
    if not path.exists():
        return [], []
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT event_id,host_id,observed_at,digest,payload FROM evidence ORDER BY observed_at DESC,event_id DESC LIMIT 1000").fetchall()
    history = []
    current = now or datetime.now(timezone.utc)
    for event_id, host_id, observed_at, digest, raw in rows:
        if hashlib.sha256(raw.encode()).hexdigest() != digest:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        try:
            message = verify_receipt(obj, key, rules_sha, now=observe_time(obj.get("observed_at")))
        except ValueError:
            continue
        if message.get("event_id") != event_id or message.get("host_id") != host_id or message.get("observed_at") != observed_at or host_id not in HOSTS:
            continue
        history.append(message)
    latest = {h: None for h in HOSTS}
    for obj in history:
        h = obj["host_id"]
        if latest[h] is None:
            latest[h] = obj
    hosts = []
    for hid, name in HOSTS.items():
        obj = latest[hid]
        age = None
        if obj:
            try:
                age = (current - observe_time(obj["observed_at"])).total_seconds()
            except ValueError:
                age = None
        fresh = age is not None and -5 <= age <= MAX_AGE_SECONDS
        ready = bool(fresh and obj and all(obj.get("gates", {}).get(k) is True for k in GATES))
        hosts.append({"id": hid, "name": name, "ready_for_work": ready, "verified_external": bool(obj), "fresh": fresh, "observed_at": obj.get("observed_at") if obj else None, "version": obj.get("runner", {}).get("version") if obj else None, "labels": obj.get("runner", {}).get("labels") if obj else [], "rules_sha": obj.get("rules_sha") if obj else None, "gates": obj.get("gates") if obj else {}, "block": obj.get("block") if obj else "admissao", "next_action": obj.get("next_action") if obj else "Obter recibo atual do Gateway e da API oficial, sem executar worker", "requires_human": obj.get("requires_human") if obj else None, "evidence_id": obj.get("event_id") if obj else None, "reason": "READY_WITH_SIGNED_EVIDENCE" if ready else "STALE_OR_MISSING_GATE" if obj else "NO_EXTERNAL_EVIDENCE"})
    safe_history = [{"event_id": h["event_id"], "host_id": h["host_id"], "observed_at": h["observed_at"], "source_sha": h["source_sha"], "block": h["block"]} for h in history[:100]]
    return hosts, safe_history


def handler_factory(db_path, viewer_token, html_path, attest_key, rules_sha):
    class Handler(BaseHTTPRequestHandler):
        def authorized(self):
            header = self.headers.get("Authorization", "")
            if not header.startswith("Basic "):
                return False
            try:
                plain = base64.b64decode(header[6:], validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return False
            password = plain.partition(":")[2]
            return hmac.compare_digest(password, viewer_token)

        def respond(self, code, data, mime="application/json; charset=utf-8"):
            data = data if isinstance(data, bytes) else canonical(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            if code == 401:
                self.send_header("WWW-Authenticate", 'Basic realm="ReqSys Readiness DEV", charset="UTF-8"')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.authorized():
                return self.respond(401, {"error": "authentication_required"})
            url = urlsplit(self.path)
            if url.path == "/api/v1/readiness":
                try:
                    hosts, history = snapshots(db_path, attest_key, rules_sha)
                except (OSError, sqlite3.Error, ValueError):
                    return self.respond(503, {"error": "evidence_store_unavailable", "ready_for_work": False})
                return self.respond(200, {"schema_version": "1", "hosts": hosts, "history": history, "continuity_certified": False, "selected_host": next((h["id"] for h in hosts if h["ready_for_work"]), None), "source": "signed_validator_receipts", "storage": "sqlite_read_only", "note": "Readback de armazenamento não certifica retomada física entre computadores"})
            if url.path in ("/", "/index.html"):
                return self.respond(200, html_path.read_bytes(), "text/html; charset=utf-8")
            return self.respond(404, {"error": "not_found"})

        def do_POST(self):
            return self.respond(405, {"error": "read_only"})
        do_PUT = do_DELETE = do_PATCH = do_POST

        def log_message(self, format, *args):
            # Nunca registrar headers/tokens nem URLs contendo query sensível.
            pass

    return Handler


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("serve")
    start.add_argument("--port", type=int, default=8765)
    imp = sub.add_parser("ingest")
    imp.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)
    db_path = os.environ.get("REQSYS_READINESS_DB", "")
    if not db_path or not Path(db_path).is_absolute():
        parser.error("REQSYS_READINESS_DB precisa ser caminho absoluto")
    key = os.environ.get("REQSYS_READINESS_ATTEST_KEY", "")
    rules_sha = os.environ.get("REQSYS_READINESS_RULES_SHA", "")
    if len(key) < 32 or not SHA40(rules_sha):
        parser.error("configuração do validador independente ausente")
    if args.command == "ingest":
        response = ingest(db_path, json.loads(args.receipt.read_text(encoding="utf-8")), key, rules_sha)
        print(canonical(response))
        return 0
    token = os.environ.get("REQSYS_READINESS_VIEWER_TOKEN", "")
    if len(token) < 24:
        parser.error("REQSYS_READINESS_VIEWER_TOKEN ausente/fraco")
    if args.port < 0 or args.port > 65535:
        parser.error("porta inválida")
    html_path = Path(__file__).resolve().parents[1] / "index.html"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_factory(db_path, token, html_path, key, rules_sha))
    print(f"API de consulta somente leitura em http://127.0.0.1:{server.server_port} (DEV loopback)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
