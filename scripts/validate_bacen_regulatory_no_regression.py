#!/usr/bin/env python3
"""Gate 1.5 BACEN: compara status derivados em base/head com o mesmo instante T."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts.bacen_derived_status import derive_status, parse_utc
except ImportError:  # execução direta a partir de scripts/
    from bacen_derived_status import derive_status, parse_utc

BASELINE_PATH = "governance/bacen/normative/NORMATIVE-BASELINE-V2.yaml"
DEFAULT_EVIDENCE_REGISTRY = "governance/bacen/normative/EVIDENCE-REGISTRY.yaml"

STATUS_RANK = {
    "nao_avaliado": 0,
    "lacuna": 1,
    "parcial": 2,
    "implementado": 3,
    "evidenciado": 4,
}


def git_show_text(ref: str, path: str, *, optional: bool = False) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        return proc.stdout
    if optional:
        return None
    raise RuntimeError(f"não foi possível ler {path} em {ref}: {proc.stderr.strip()}")


def load_yaml_at_ref(ref: str, path: str, *, optional: bool = False) -> dict[str, Any] | None:
    raw = git_show_text(ref, path, optional=optional)
    if raw is None:
        return None
    loaded = yaml.safe_load(raw)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} deve conter objeto YAML no topo")
    return loaded


def normalize_applicability(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    if not decision:
        return None
    value = decision.get("decision")
    if value not in {"not_applicable", "nao_aplicavel"}:
        return None
    normalized = dict(decision)
    normalized["decision"] = "nao_aplicavel"
    return normalized


def load_snapshot_inputs(ref: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[dict[str, Any]]]:
    baseline = load_yaml_at_ref(ref, BASELINE_PATH)
    assert baseline is not None
    baseline_meta = baseline.get("normative_baseline") or {}
    obligations: list[dict[str, Any]] = []
    for item in baseline_meta.get("obligation_sets") or []:
        path = item.get("path")
        selector = item.get("selector", "obligations")
        if not path:
            raise ValueError("obligation_set sem path")
        source = load_yaml_at_ref(ref, str(path))
        assert source is not None
        selected = source.get(selector) or []
        if not isinstance(selected, list):
            raise ValueError(f"selector {selector} em {path} deve ser lista")
        obligations.extend(selected)

    evidence_path = baseline_meta.get("evidence_registry", DEFAULT_EVIDENCE_REGISTRY)
    evidence_doc = load_yaml_at_ref(ref, str(evidence_path), optional=True)
    evidences = [] if evidence_doc is None else list(evidence_doc.get("evidences") or [])
    applicability = baseline.get("applicability")
    return obligations, applicability, evidences


def derive_snapshot(
    *,
    obligations: list[dict[str, Any]],
    applicability: dict[str, Any] | None,
    evidences: list[dict[str, Any]],
    as_of: str,
) -> dict[str, str]:
    parse_utc(as_of)
    result: dict[str, str] = {}
    seen: set[str] = set()
    family_decision = normalize_applicability(applicability)
    for obligation in obligations:
        uid = str(obligation.get("uid") or "")
        if not uid:
            raise ValueError("obrigação sem uid")
        if uid in seen:
            raise ValueError(f"uid duplicado: {uid}")
        seen.add(uid)
        decision = normalize_applicability(obligation.get("applicability_decision")) or family_decision
        result[uid] = derive_status(
            obligation=obligation,
            as_of=as_of,
            assessment=obligation.get("assessment"),
            applicability_decision=decision,
            evidences=evidences,
        )
    return result


def compare_snapshots(base: dict[str, str], head: dict[str, str]) -> dict[str, Any]:
    regressions: list[dict[str, str]] = []
    improvements: list[dict[str, str]] = []
    unchanged = 0
    added: list[str] = []

    for uid, base_status in sorted(base.items()):
        if uid not in head:
            regressions.append({
                "uid": uid,
                "base_status": base_status,
                "head_status": "obrigacao_removida",
                "reason": "obligation_removed",
            })
            continue
        head_status = head[uid]
        if base_status == head_status:
            unchanged += 1
            continue
        if head_status == "nao_aplicavel" and base_status != "nao_aplicavel":
            regressions.append({
                "uid": uid,
                "base_status": base_status,
                "head_status": head_status,
                "reason": "applicability_scope_reduction",
            })
            continue
        if base_status == "nao_aplicavel" and head_status != "nao_aplicavel":
            improvements.append({
                "uid": uid,
                "base_status": base_status,
                "head_status": head_status,
                "reason": "applicability_scope_expansion",
            })
            continue
        if base_status not in STATUS_RANK or head_status not in STATUS_RANK:
            raise ValueError(f"transição de status não comparável: {base_status} -> {head_status}")
        if STATUS_RANK[head_status] < STATUS_RANK[base_status]:
            regressions.append({
                "uid": uid,
                "base_status": base_status,
                "head_status": head_status,
                "reason": "derived_status_regression",
            })
        else:
            improvements.append({
                "uid": uid,
                "base_status": base_status,
                "head_status": head_status,
                "reason": "derived_status_improvement",
            })

    for uid in sorted(set(head) - set(base)):
        added.append(uid)

    return {
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "added": added,
    }


def evaluate_refs(*, base_ref: str, head_ref: str, as_of: str) -> dict[str, Any]:
    parse_utc(as_of)
    base_inputs = load_snapshot_inputs(base_ref)
    head_inputs = load_snapshot_inputs(head_ref)
    base_snapshot = derive_snapshot(
        obligations=base_inputs[0], applicability=base_inputs[1], evidences=base_inputs[2], as_of=as_of
    )
    head_snapshot = derive_snapshot(
        obligations=head_inputs[0], applicability=head_inputs[1], evidences=head_inputs[2], as_of=as_of
    )
    comparison = compare_snapshots(base_snapshot, head_snapshot)
    return {
        "schema_version": "1.0.0",
        "gate": "BACEN Regulatory No Regression Gate 1.5",
        "result": "invalid" if comparison["regressions"] else "valid",
        "base_ref": base_ref,
        "head_ref": head_ref,
        "as_of": as_of,
        "frozen_time": True,
        "same_as_of_for_base_and_head": True,
        "base_obligations": len(base_snapshot),
        "head_obligations": len(head_snapshot),
        "regression_count": len(comparison["regressions"]),
        "improvement_count": len(comparison["improvements"]),
        "unchanged_count": comparison["unchanged"],
        "added_count": len(comparison["added"]),
        **comparison,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--head-ref", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument(
        "--output",
        default="artifacts/bacen/bacen-regulatory-no-regression.json",
    )
    args = parser.parse_args()

    result = evaluate_refs(base_ref=args.base_ref, head_ref=args.head_ref, as_of=args.as_of)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
