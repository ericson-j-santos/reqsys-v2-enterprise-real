#!/usr/bin/env python3
"""Evaluate whether one ReqSys environment is safe for automatic promotion."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


def load_json_object(path: str | Path) -> tuple[dict[str, Any], str | None]:
    file_path = Path(path)
    if not file_path.exists():
        return {}, f"artifact_missing:{file_path}"
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"artifact_invalid:{file_path}:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return {}, f"artifact_not_object:{file_path}"
    return payload, None


def normalize_sha(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"[0-9a-fA-F]{7,40}", text)
    return (match.group(0) if match else text)[:12].lower()


def _check(check_id: str, ok: bool, detail: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "ok": bool(ok),
        "status": "passed" if ok else "blocked",
        "detail": detail,
    }


def _single_environment(
    payload: dict[str, Any],
    environment: str,
) -> dict[str, Any] | None:
    for item in payload.get("environments") or []:
        if isinstance(item, dict) and str(item.get("environment")) == environment:
            return item
    return None


def evaluate_capture(
    *,
    environment: str,
    expected_sha: str,
    fly_state: dict[str, Any],
    runtime: dict[str, Any],
    publication: dict[str, Any],
    login: dict[str, Any],
    fly_state_error: str | None = None,
    runtime_error: str | None = None,
    publication_error: str | None = None,
    login_error: str | None = None,
    observed_at_epoch: int | None = None,
) -> dict[str, Any]:
    if environment not in {"dev", "hml", "prod"}:
        raise ValueError(f"unsupported_environment:{environment}")
    expected = normalize_sha(expected_sha)
    if len(expected) < 7:
        raise ValueError("expected_sha_invalid")

    checks: list[dict[str, Any]] = []
    checks.append(
        _check(
            "fly_state_integrity",
            fly_state_error is None
            and fly_state.get("contract") == "fly-environment-state-capture",
            fly_state_error or f"contract={fly_state.get('contract')}",
        )
    )
    checks.append(
        _check(
            "runtime_integrity",
            runtime_error is None
            and runtime.get("contract") == "public-runtime-smoke-readiness",
            runtime_error or f"contract={runtime.get('contract')}",
        )
    )
    checks.append(
        _check(
            "publication_integrity",
            publication_error is None
            and publication.get("contract") == "publication-sync-validation",
            publication_error or f"contract={publication.get('contract')}",
        )
    )
    checks.append(
        _check(
            "login_integrity",
            login_error is None
            and login.get("contract") == "multi-environment-login-validation",
            login_error or f"contract={login.get('contract')}",
        )
    )

    fly_env = str(fly_state.get("environment") or "")
    runtime_env = str(runtime.get("environment") or "")
    publication_env = _single_environment(publication, environment)
    login_env = _single_environment(login, environment)
    environment_consistent = (
        fly_env == environment
        and runtime_env == environment
        and publication_env is not None
        and login_env is not None
    )
    checks.append(
        _check(
            "environment_consistency",
            environment_consistent,
            (
                f"fly={fly_env or 'missing'} runtime={runtime_env or 'missing'} "
                f"publication={bool(publication_env)} login={bool(login_env)}"
            ),
        )
    )

    fly_sha = normalize_sha(fly_state.get("expected_sha"))
    observed_sha = normalize_sha(
        (publication_env or {}).get("observed", {}).get("sha")
    )
    publication_expected = normalize_sha(
        (publication_env or {}).get("expected", {}).get("sha")
    )
    sha_consistent = (
        fly_sha == expected
        and publication_expected == expected
        and observed_sha == expected
    )
    checks.append(
        _check(
            "sha_consistency",
            sha_consistent,
            (
                f"expected={expected} fly={fly_sha or 'missing'} "
                f"publication_expected={publication_expected or 'missing'} "
                f"observed={observed_sha or 'missing'}"
            ),
        )
    )

    fly_ready = (
        fly_state.get("ready") is True
        and not (fly_state.get("blocking_issues") or [])
    )
    checks.append(
        _check(
            "fly_state_ready",
            fly_ready,
            (
                f"ready={fly_state.get('ready')} "
                f"blockers={len(fly_state.get('blocking_issues') or [])}"
            ),
        )
    )

    required_total = int(runtime.get("total") or 0)
    required_ok = int(runtime.get("ok") or 0)
    readiness = (
        runtime.get("readiness")
        if isinstance(runtime.get("readiness"), dict)
        else {}
    )
    runtime_ready = (
        required_total > 0
        and required_ok == required_total
        and readiness.get("api_ready") is True
        and readiness.get("runtime_ready") is True
        and not (readiness.get("blocking_issues") or [])
    )
    checks.append(
        _check(
            "runtime_ready",
            runtime_ready,
            (
                f"required={required_ok}/{required_total} "
                f"api_ready={readiness.get('api_ready')} "
                f"runtime_ready={readiness.get('runtime_ready')}"
            ),
        )
    )

    publication_ready = (
        publication.get("ok") is True
        and publication_env is not None
        and publication_env.get("synced") is True
        and not (publication_env.get("blocking_issues") or [])
    )
    checks.append(
        _check(
            "publication_synced",
            publication_ready,
            (
                f"overall={publication.get('ok')} "
                f"environment_synced={(publication_env or {}).get('synced')}"
            ),
        )
    )

    login_ready = (
        login.get("ok") is True
        and login_env is not None
        and login_env.get("login_ready") is True
        and not (login_env.get("errors") or [])
    )
    checks.append(
        _check(
            "login_ready",
            login_ready,
            (
                f"overall={login.get('ok')} "
                f"environment_ready={(login_env or {}).get('login_ready')}"
            ),
        )
    )

    failed = [item for item in checks if not item["ok"]]
    ready = not failed
    return {
        "schema_version": "1.0.0",
        "contract": "automatic-environment-promotion-capture",
        "generated_at_epoch": int(
            observed_at_epoch if observed_at_epoch is not None else time.time()
        ),
        "environment": environment,
        "expected_sha": expected,
        "ready": ready,
        "decision": (
            "promotion_stage_ready" if ready else "promotion_stage_blocked"
        ),
        "checks": checks,
        "blocking_issues": [item["id"] for item in failed],
        "automatic_promotion_allowed": ready,
        "production_touched": fly_state.get("production_touched") is True,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Promoção automática — {report['environment']}",
        "",
        f"- Decision: `{report['decision']}`",
        f"- Expected SHA: `{report['expected_sha']}`",
        (
            "- Automatic promotion allowed: "
            f"`{str(report['automatic_promotion_allowed']).lower()}`"
        ),
        "",
        "## Checks",
    ]
    for check in report["checks"]:
        lines.append(
            f"- `{check['status']}` {check['id']} — {check['detail']}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate automatic environment promotion capture"
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=["dev", "hml", "prod"],
    )
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--fly-state", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--publication", required=True)
    parser.add_argument("--login", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    fly_state, fly_error = load_json_object(args.fly_state)
    runtime, runtime_error = load_json_object(args.runtime)
    publication, publication_error = load_json_object(args.publication)
    login, login_error = load_json_object(args.login)
    report = evaluate_capture(
        environment=args.environment,
        expected_sha=args.expected_sha,
        fly_state=fly_state,
        runtime=runtime,
        publication=publication,
        login=login,
        fly_state_error=fly_error,
        runtime_error=runtime_error,
        publication_error=publication_error,
        login_error=login_error,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output.parent / "summary.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "environment": args.environment,
                "ready": report["ready"],
                "blocking_issues": report["blocking_issues"],
            },
            ensure_ascii=False,
        )
    )
    return 1 if args.strict and not report["ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
