#!/usr/bin/env python3
"""Gera o manifesto canônico de admissão CI a partir da evidência READY_FOR_PR."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")

REQUIRED_PREVENTIVE_INVARIANTS = {
    "sdd:contract",
    "security:changed-diff",
    "workflow:surface-budget",
    "workflow:regression-contracts",
}

PROFILE_WORKFLOWS = {
    "backend": {"CI — ReqSys v2 Enterprise", "CI Enterprise Fast"},
    "frontend": {"CI — ReqSys v2 Enterprise", "CI Enterprise Fast", "CI E2E Governado"},
    "operational": {"CI — ReqSys v2 Enterprise", "CI Enterprise Fast"},
    "general": {"CI — ReqSys v2 Enterprise", "CI Enterprise Fast"},
    "docs_only": set(),
}


class AdmissionError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_blocker(message: str) -> str:
    text = message.casefold()
    if "head divergente" in text or " commit(s) atrás " in text or "atrás de" in text:
        return "SOURCE_STALE"
    if "nenhuma alteração" in text:
        return "EMPTY_CHANGE"
    if any(token in text for token in ("sdd:contract", "json:", "yaml:", "workflow sem")):
        return "CONTRACT_INVALID"
    if "preventive invariant" in text or any(name in text for name in REQUIRED_PREVENTIVE_INVARIANTS):
        return "PREVENTIVE_INVARIANT_FAILED"
    if any(token in text for token in ("pytest", "ruff", "py_compile", "frontend:build", "bash-n")):
        return "CODE_FAILURE"
    return "UNKNOWN_BLOCKER"


def normalize_preventive_invariants(readiness: dict[str, Any]) -> tuple[list[dict[str, str]], list[str]]:
    raw = readiness.get("preventive_invariants")
    if not isinstance(raw, list):
        return [], ["preventive invariants ausentes"]

    normalized: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        detail = str(item.get("detail") or "").strip()
        if not name:
            continue
        if name in normalized:
            errors.append(f"preventive invariant duplicado: {name}")
            continue
        normalized[name] = {"name": name, "status": status or "missing", "detail": detail}

    for name in sorted(REQUIRED_PREVENTIVE_INVARIANTS):
        item = normalized.get(name)
        if item is None:
            errors.append(f"preventive invariant ausente: {name}")
        elif item["status"] != "passed":
            errors.append(f"preventive invariant falhou: {name}: status={item['status']}")

    return [normalized[name] for name in sorted(normalized)], errors


def required_workflows(profiles: list[str]) -> list[str]:
    workflows = {"Pre-PR Readiness Gate"}
    for profile in profiles:
        workflows.update(PROFILE_WORKFLOWS.get(profile, {"CI — ReqSys v2 Enterprise", "CI Enterprise Fast"}))
    return sorted(workflows)


def build_manifest(readiness: dict[str, Any], expected_head_sha: str = "") -> dict[str, Any]:
    if not isinstance(readiness, dict):
        raise AdmissionError("readiness_payload_invalid")

    head_sha = str(readiness.get("head_sha") or "").strip().lower()
    base_sha = str(readiness.get("base_sha") or "").strip().lower()
    if not SHA40.fullmatch(head_sha):
        raise AdmissionError("head_sha_invalid")
    if not SHA40.fullmatch(base_sha):
        raise AdmissionError("base_sha_invalid")

    expected = expected_head_sha.strip().lower()
    if expected and expected != head_sha:
        raise AdmissionError(f"head_sha_mismatch:expected={expected}:observed={head_sha}")

    profiles = [str(item) for item in (readiness.get("profiles") or []) if str(item).strip()]
    changed = [str(item) for item in (readiness.get("changed_files") or []) if str(item).strip()]
    blockers = [str(item) for item in (readiness.get("blockers") or []) if str(item).strip()]
    readiness_status = str(readiness.get("status") or "").strip().lower()
    try:
        behind_by = int(readiness.get("behind_by") or 0)
    except (TypeError, ValueError) as exc:
        raise AdmissionError("behind_by_invalid") from exc

    preventive_invariants, invariant_errors = normalize_preventive_invariants(readiness)
    manifest_blockers = list(blockers)
    manifest_blockers.extend(invariant_errors)
    if behind_by != 0:
        manifest_blockers.append(f"source stale: behind_by={behind_by}")
    admitted = readiness_status == "passed" and not manifest_blockers

    return {
        "schema_version": "1.1.0",
        "manifest_type": "reqsys_ci_admission",
        "generated_at_utc": utc_now(),
        "status": "admitted" if admitted else "blocked",
        "correlation_id": str(readiness.get("correlation_id") or ""),
        "head_sha": head_sha,
        "base_ref": str(readiness.get("base_ref") or "main"),
        "base_sha": base_sha,
        "classification": {
            "profiles": sorted(set(profiles)),
            "changed_files_count": len(changed),
            "changed_files": changed,
        },
        "required_workflows": required_workflows(profiles),
        "preventive_invariants": preventive_invariants,
        "dependencies": [
            {
                "name": "pre_pr_readiness",
                "required": True,
                "status": readiness_status or "unknown",
                "evidence_path": "artifacts/pre-pr-readiness/pre-pr-readiness.json",
            },
            {
                "name": "ollama_ci_triage",
                "required": False,
                "role": "accelerator",
                "failure_policy": "deterministic_fallback",
            },
        ],
        "evidence": [
            {
                "type": "pre_pr_readiness",
                "head_sha": head_sha,
                "base_sha": base_sha,
                "status": readiness_status or "unknown",
                "correlation_id": str(readiness.get("correlation_id") or ""),
            }
        ],
        "blocker_reason": [
            {"code": classify_blocker(message), "message": message}
            for message in manifest_blockers
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera manifesto de admissão CI do HEAD atual.")
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--expected-head-sha", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        readiness = json.loads(args.readiness.read_text(encoding="utf-8"))
        manifest = build_manifest(readiness, args.expected_head_sha)
    except (OSError, json.JSONDecodeError, AdmissionError) as exc:
        print(json.dumps({"result": "CI_ADMISSION_MANIFEST_BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
