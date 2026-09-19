from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"control plane unavailable: {type(exc.reason).__name__}") from exc


def cmd_intake(args: argparse.Namespace) -> None:
    payload = {
        "event_id": args.event_id,
        "correlation_id": args.correlation_id,
        "idempotency_key": args.idempotency_key,
        "task_type": args.task_type,
        "payload": {
            "repository": args.repository,
            **({"target_host": args.target_host} if args.target_host else {}),
            **({"action_id": args.action_id} if args.action_id else {}),
            **({"delay_seconds": args.delay_seconds} if args.delay_seconds is not None else {}),
        },
        "risk": args.risk,
        "max_attempts": args.max_attempts,
        "lease_seconds": args.lease_seconds,
    }
    status, response = request_json(
        "POST",
        args.endpoint.rstrip("/") + "/v1/intake",
        payload,
    )
    if status not in (200, 201):
        print(json.dumps({"status": status, "response": response}, sort_keys=True))
        raise SystemExit(2)

    dispatch = response.get("dispatch")
    selected = dispatch["worker"]["worker_id"] if dispatch else None
    if args.expect_worker and selected != args.expect_worker:
        raise SystemExit(
            f"dispatch mismatch: expected {args.expect_worker}, observed {selected}"
        )
    if args.expect_no_dispatch and dispatch is not None:
        raise SystemExit("expected no dispatch")
    if args.expect_replayed and response.get("replayed") is not True:
        raise SystemExit("expected replayed=true")

    print(
        json.dumps(
            {
                "ok": True,
                "status": status,
                "item_id": response["item"]["id"],
                "item_status": response["item"]["status"],
                "target_worker": response["item"]["target_worker"],
                "selected_worker": selected,
                "dispatch_id": dispatch["dispatch_id"] if dispatch else None,
                "replayed": response.get("replayed", False),
                "correlation_id": args.correlation_id,
            },
            sort_keys=True,
        )
    )


def cmd_status(args: argparse.Namespace) -> None:
    status, response = request_json(
        "GET",
        args.endpoint.rstrip("/") + "/v1/status",
    )
    if status != 200:
        raise SystemExit(2)
    worker_ids = sorted(
        worker["worker_id"] for worker in response.get("workers", {}).get("workers", [])
    )
    expected = sorted(args.expect_worker or [])
    if expected and worker_ids != expected:
        raise SystemExit(
            f"worker registry mismatch: expected {expected}, observed {worker_ids}"
        )
    print(
        json.dumps(
            {
                "ok": True,
                "workers": worker_ids,
                "eligible_workers": response.get("workers", {}).get("eligible"),
                "dispatch_events": response.get("workers", {}).get("dispatch_events"),
                "by_status": response.get("by_status", {}),
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    intake = sub.add_parser("intake")
    intake.add_argument("--event-id", required=True)
    intake.add_argument("--correlation-id", required=True)
    intake.add_argument("--idempotency-key", required=True)
    intake.add_argument("--task-type", required=True)
    intake.add_argument("--repository", default="reqsys-v2-enterprise-real")
    intake.add_argument("--target-host")
    intake.add_argument("--action-id")
    intake.add_argument("--delay-seconds", type=int)
    intake.add_argument("--risk", type=int, default=1)
    intake.add_argument("--max-attempts", type=int, default=3)
    intake.add_argument("--lease-seconds", type=int, default=60)
    intake.add_argument("--expect-worker")
    intake.add_argument("--expect-no-dispatch", action="store_true")
    intake.add_argument("--expect-replayed", action="store_true")
    intake.set_defaults(func=cmd_intake)

    status = sub.add_parser("status")
    status.add_argument("--expect-worker", action="append")
    status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
