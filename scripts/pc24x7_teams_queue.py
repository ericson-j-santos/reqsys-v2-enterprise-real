#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_ROOT = Path(os.getenv("PC24X7_TEAMS_QUEUE_ROOT", "/var/lib/reqsys-24x7/teams"))
MAX_ATTEMPTS = int(os.getenv("PC24X7_TEAMS_MAX_ATTEMPTS", "5"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def ensure_dirs(root: Path) -> None:
    for name in ("pending", "processing", "done", "quarantine", "evidence"):
        (root / name).mkdir(parents=True, exist_ok=True)


def build_job(*, provider: str, model: str, mensagem: str, titulo: str, correlation_id: str | None = None) -> dict:
    business = {
        "provider": provider,
        "model": model,
        "mensagem": mensagem,
        "titulo": titulo,
        "data_classification": "internal",
        "tenant_id": "reqsys-dev",
        "area_id": "teams-gateway",
        "requester_id": "pc24x7-worker",
        "cost_center": "dev",
        "origem": "pc24x7",
        "teams_destino_tipo": "chat_1a1",
        "teams_modo": "bot",
        "enviar_teams": True,
    }
    digest = canonical_hash(business)
    business["idempotency_key"] = f"pc24x7:{digest}"
    return {
        "schema_version": "1.0.0",
        "job_id": str(uuid.uuid4()),
        "correlation_id": correlation_id or f"pc24x7-teams-{uuid.uuid4()}",
        "payload_sha256": digest,
        "attempts": 0,
        "created_at": utcnow(),
        "not_before": 0,
        "payload": business,
    }


def enqueue(root: Path, job: dict) -> Path:
    ensure_dirs(root)
    digest = job["payload_sha256"]
    for bucket in ("pending", "processing", "done"):
        existing = list((root / bucket).glob(f"*-{digest}.json"))
        if existing:
            return existing[0]
    target = root / "pending" / f"{job['job_id']}-{digest}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def read_token(path: Path) -> str:
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("service token file is empty")
    return token


def call_reqsys(base_url: str, token: str, job: dict) -> dict:
    body = json.dumps(job["payload"], ensure_ascii=False).encode("utf-8")
    req = Request(
        base_url.rstrip("/") + "/v1/teams-gateway/ai-conversations",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Service-Token": token,
            "X-Correlation-Id": job["correlation_id"],
        },
    )
    with urlopen(req, timeout=90) as response:  # noqa: S310 - URL comes from controlled config.
        return json.loads(response.read().decode("utf-8"))


def sanitize_result(job: dict, response: dict | None, *, status: str, error: str | None = None) -> dict:
    data = (response or {}).get("data") or {}
    conversation = data.get("conversation") or {}
    teams = data.get("teams") or {}
    delivery = teams.get("entrega") or {}
    return {
        "schema_version": "1.0.0",
        "job_id": job["job_id"],
        "status": status,
        "correlation_id": job["correlation_id"],
        "payload_sha256": job["payload_sha256"],
        "attempts": job["attempts"],
        "conversation_id": conversation.get("id"),
        "duplicate": data.get("duplicate"),
        "teams_delivered": bool(delivery.get("entregue")),
        "teams_channel": delivery.get("canal_usado"),
        "error": error,
        "finished_at": utcnow(),
        "secret_value_exposed": False,
    }


def process_one(root: Path, base_url: str, token_file: Path) -> dict | None:
    ensure_dirs(root)
    candidates = sorted((root / "pending").glob("*.json"))
    now = time.time()
    selected = None
    job = None
    for candidate in candidates:
        loaded = json.loads(candidate.read_text(encoding="utf-8"))
        if float(loaded.get("not_before") or 0) <= now:
            selected, job = candidate, loaded
            break
    if selected is None or job is None:
        return None

    processing = root / "processing" / selected.name
    selected.replace(processing)
    job["attempts"] = int(job.get("attempts") or 0) + 1
    response = None
    try:
        response = call_reqsys(base_url, read_token(token_file), job)
        evidence = sanitize_result(job, response, status="done")
        target = root / "done" / processing.name
        processing.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        processing.replace(target)
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
        if job["attempts"] >= MAX_ATTEMPTS:
            evidence = sanitize_result(job, response, status="quarantined", error=type(exc).__name__)
            target = root / "quarantine" / processing.name
        else:
            backoff = min(300, 2 ** job["attempts"])
            job["not_before"] = time.time() + backoff
            evidence = sanitize_result(job, response, status="retry", error=type(exc).__name__)
            target = root / "pending" / processing.name
        processing.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        processing.replace(target)

    evidence_path = root / "evidence" / f"{job['job_id']}-{job['attempts']}.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


def run_worker(root: Path, base_url: str, token_file: Path, once: bool, interval: int) -> int:
    while True:
        result = process_one(root, base_url, token_file)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False))
        if once:
            return 0
        time.sleep(interval if result is None else 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PC24x7 durable Teams AI conversation queue")
    parser.add_argument("--root", default=str(DEFAULT_ROOT))
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("enqueue")
    add.add_argument("--provider", default="gemini")
    add.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    add.add_argument("--mensagem", required=True)
    add.add_argument("--titulo", default="ReqSys 24x7 Teams DEV")
    add.add_argument("--correlation-id")
    worker = sub.add_parser("worker")
    worker.add_argument("--base-url", default=os.getenv("REQSYS_API_BASE_URL", "https://reqsys-api-dev.fly.dev"))
    worker.add_argument("--token-file", default=os.getenv("REQSYS_API_SERVICE_TOKEN_FILE", "/run/secrets/reqsys_api_service_token"))
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--interval", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    if args.command == "enqueue":
        path = enqueue(root, build_job(provider=args.provider, model=args.model, mensagem=args.mensagem, titulo=args.titulo, correlation_id=args.correlation_id))
        print(json.dumps({"queued": True, "path": str(path), "secret_value_exposed": False}))
        return 0
    return run_worker(root, args.base_url, Path(args.token_file), args.once, args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
