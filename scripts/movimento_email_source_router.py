#!/usr/bin/env python3
"""Roteia a origem da Prospecção Movimento em DEV sem mascarar aceite corporativo.

Modos:
- corporate: exige a origem corporativa e falha fechado;
- equivalent-dev: usa explicitamente a equivalência sintética DEV;
- auto: usa corporate somente quando configuração e DNS estão prontos;
        caso contrário usa a equivalência DEV apenas para continuidade DEV.

Nunca promove equivalência DEV como evidência corporativa.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
CORPORATE_SCRIPT = ROOT / "scripts" / "sincronizar_movimento_email_corporate.py"
EQUIVALENT_SCRIPT = ROOT / "scripts" / "movimento_email_equivalent_dev.py"


def _load_corporate_module():
    spec = importlib.util.spec_from_file_location("movimento_email_corporate", CORPORATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("corporate_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _present(env: Mapping[str, str], key: str) -> bool:
    return bool(str(env.get(key, "")).strip())


def _secret_state(env: Mapping[str, str], key: str) -> str:
    direct = _present(env, key)
    file_ref = _present(env, f"{key}_FILE")
    if direct and file_ref:
        return "ambiguous"
    if direct or file_ref:
        return "configured"
    return "missing"


def configuration_state(env: Mapping[str, str]) -> dict[str, str]:
    return {
        "source": _secret_state(env, "MOVIMENTO_EMAIL_SOURCE_DSN"),
        "target": _secret_state(env, "MOVIMENTO_EMAIL_TARGET_DSN"),
    }


def _dns_resolves(host: str) -> bool:
    try:
        return bool(socket.getaddrinfo(host, None, type=socket.SOCK_STREAM))
    except OSError:
        return False


def _dsn_host(dsn: str, corporate_module: Any) -> str:
    raw = (
        corporate_module.dsn_value(dsn, "Server")
        or corporate_module.dsn_value(dsn, "Data Source")
    ).strip()
    if not raw:
        raise RuntimeError("source_dsn_server_missing")
    # host,1433 ou host\\instancia: DNS é validado somente pelo host.
    host = raw.split(",", 1)[0].split("\\", 1)[0].strip()
    if not host:
        raise RuntimeError("source_dsn_server_missing")
    return host


def select_route(
    mode: str,
    env: Mapping[str, str],
    *,
    dns_resolver: Callable[[str], bool] = _dns_resolves,
    corporate_module: Any | None = None,
) -> dict[str, Any]:
    if mode not in {"auto", "corporate", "equivalent-dev"}:
        raise ValueError("invalid_mode")

    state = configuration_state(env)
    result: dict[str, Any] = {
        "requested_mode": mode,
        "configuration_state": state,
        "selected_source": None,
        "fallback_used": False,
        "fallback_reason": None,
        "hard_block": None,
    }

    if mode == "equivalent-dev":
        result["selected_source"] = "equivalent-dev"
        return result

    if "ambiguous" in state.values():
        result["hard_block"] = "ambiguous_dsn_configuration"
        return result

    if mode == "corporate":
        if "missing" in state.values():
            result["hard_block"] = "corporate_dsn_configuration_missing"
            return result
    elif "missing" in state.values():
        result.update(
            selected_source="equivalent-dev",
            fallback_used=True,
            fallback_reason="corporate_dsn_configuration_missing",
        )
        return result

    module = corporate_module or _load_corporate_module()
    try:
        source_dsn = module.read_secret("MOVIMENTO_EMAIL_SOURCE_DSN")
        module.validate_source_dsn(source_dsn)
        host = _dsn_host(source_dsn, module)
    except Exception as exc:
        # DSN presente porém inválido não deve ser mascarado por fallback.
        result["hard_block"] = type(exc).__name__ + ":" + str(exc).splitlines()[0][:160]
        return result

    if not dns_resolver(host):
        if mode == "auto":
            result.update(
                selected_source="equivalent-dev",
                fallback_used=True,
                fallback_reason="corporate_source_dns_unavailable",
            )
        else:
            result["hard_block"] = "corporate_source_dns_unavailable"
        return result

    result["selected_source"] = "corporate"
    return result


def _parse_last_json(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def run_equivalent() -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, str(EQUIVALENT_SCRIPT), "run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = _parse_last_json(completed.stdout)
    return completed.returncode, payload


def run_corporate(
    ref: str,
    evidence_root: Path,
    correlation_id: str,
    source_sha: str,
    mapping: str,
) -> tuple[int, dict[str, Any]]:
    phases: list[dict[str, Any]] = []
    base = [
        sys.executable,
        str(CORPORATE_SCRIPT),
        "--data-referencia", ref,
        "--correlation-id", correlation_id,
        "--source-sha", source_sha,
    ]
    if mapping:
        base += ["--mapping", mapping]

    for index, mode in enumerate(("dry-run", "apply", "apply"), start=1):
        evidence = evidence_root / f"{index:02d}-{mode}.json"
        completed = subprocess.run(
            [*base, "--mode", mode, "--evidence", str(evidence)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = (
            json.loads(evidence.read_text(encoding="utf-8"))
            if evidence.is_file()
            else _parse_last_json(completed.stdout)
        )
        phases.append({
            "mode": mode,
            "exit_code": completed.returncode,
            "status": payload.get("status"),
            "repeat_action": payload.get("repeat_action"),
            "corporate_source_validated": payload.get("corporate_source_validated", False),
        })
        if completed.returncode != 0:
            return completed.returncode, {"phases": phases, "passed": False}

    repeat = phases[-1]
    passed = (
        repeat.get("status") == "noop"
        and repeat.get("repeat_action") == "already_present_no_write"
        and repeat.get("corporate_source_validated") is True
    )
    return (0 if passed else 2), {"phases": phases, "passed": passed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("auto", "corporate", "equivalent-dev"), default="auto")
    parser.add_argument("--data-referencia", default=date.today().isoformat())
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--mapping", default=os.getenv("MOVIMENTO_EMAIL_SOURCE_MAP", "").strip())
    parser.add_argument("--source-sha", default=os.getenv("GITHUB_SHA", "").strip())
    parser.add_argument("--correlation-id", default="")
    args = parser.parse_args()

    correlation_id = args.correlation_id.strip() or f"movimento-source-router-{uuid.uuid4()}"
    decision = select_route(args.mode, os.environ)

    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "feature": "movimento_email_source_router",
        "environment": "dev",
        "correlation_id": correlation_id,
        "source_sha": args.source_sha,
        "requested_mode": args.mode,
        "selected_source": decision.get("selected_source"),
        "fallback_used": decision.get("fallback_used", False),
        "fallback_reason": decision.get("fallback_reason"),
        "configuration_state": decision.get("configuration_state"),
        "equivalent_source": False,
        "synthetic": False,
        "corporate_source_validated": False,
        "secrets_exposed": False,
        "production_touched": False,
        "passed": False,
    }

    hard_block = decision.get("hard_block")
    if hard_block:
        summary.update(status="blocked", hard_block=hard_block)
        rc = 2
    elif decision["selected_source"] == "equivalent-dev":
        rc, payload = run_equivalent()
        passed = rc == 0 and payload.get("status") == "passed"
        summary.update(
            status="passed" if passed else "blocked",
            equivalent_source=True,
            synthetic=True,
            corporate_source_validated=False,
            passed=passed,
            equivalent_result={
                "status": payload.get("status"),
                "repeat_action": (payload.get("repeat_sync") or {}).get("action"),
                "already_present_no_write": (payload.get("repeat_sync") or {}).get("already_present_no_write"),
                "view_counts": (payload.get("view_validation") or {}).get("counts", {}),
            },
        )
        rc = 0 if passed else 2
    else:
        cycle = args.evidence.parent / f"{args.evidence.stem}-corporate"
        cycle.mkdir(parents=True, exist_ok=True)
        rc, payload = run_corporate(
            args.data_referencia,
            cycle,
            correlation_id,
            args.source_sha,
            args.mapping,
        )
        passed = rc == 0 and payload.get("passed") is True
        summary.update(
            status="passed" if passed else "blocked",
            equivalent_source=False,
            synthetic=False,
            corporate_source_validated=passed,
            passed=passed,
            corporate_result=payload,
        )
        # Importante: após selecionar corporate, falha de auth/contrato não cai para equivalente.
        rc = 0 if passed else 2

    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
