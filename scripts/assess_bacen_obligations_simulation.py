#!/usr/bin/env python3
"""Avalia a baseline normativa em modo de simulação sem fabricar conformidade."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

DEFAULT_BASELINES = (
    Path("governance/bacen/normative/NORMATIVE-BASELINE.yaml"),
    Path("governance/bacen/normative/NORMATIVE-OBLIGATIONS-EXTENDED.yaml"),
)
DEFAULT_EVIDENCE = Path("governance/bacen/normative/EVIDENCE-REGISTRY.yaml")
EXPECTED_TOTAL = 57


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def evidence_index(data: dict) -> set[str]:
    refs: set[str] = set()
    for item in data.get("evidence", data.get("evidences", [])) or []:
        if not isinstance(item, dict):
            continue
        for key in ("obligation_uid", "normative_uid", "uid", "obligation_code", "code"):
            value = item.get(key)
            if value:
                refs.add(str(value))
    return refs


def iter_obligations(baselines: dict | list[dict] | tuple[dict, ...]):
    payloads = (baselines,) if isinstance(baselines, dict) else baselines
    for payload in payloads:
        for obligation in payload.get("obligations", []) or []:
            if isinstance(obligation, dict):
                yield obligation


def assess(baselines: dict | list[dict] | tuple[dict, ...], evidence: dict) -> dict:
    refs = evidence_index(evidence)
    rows = []
    for obligation in iter_obligations(baselines):
        uid = str(obligation.get("uid", ""))
        code = str(obligation.get("code", ""))
        conditional = code.startswith("CMN4893-ART3A") or code.startswith("CMN4893-ART22B")
        has_evidence = uid in refs or code in refs
        rows.append({
            "uid": uid,
            "code": code,
            "title": obligation.get("title"),
            "conditional": conditional,
            "status": "EVIDENCIA_LOCALIZADA_PARA_REVISAO" if has_evidence else "EVIDENCIA_AUSENTE",
            "compliance_claim": False,
        })
    return {
        "mode": "SIMULATION_ONLY",
        "institutional_validity": False,
        "production_allowed": False,
        "total": len(rows),
        "evidence_candidates": sum(r["status"] == "EVIDENCIA_LOCALIZADA_PARA_REVISAO" for r in rows),
        "evidence_missing": sum(r["status"] == "EVIDENCIA_AUSENTE" for r in rows),
        "conditional": sum(r["conditional"] for r in rows),
        "obligations": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        dest="baselines",
        type=Path,
        action="append",
        help="Baseline normativa. Pode ser repetida para compor o conjunto completo.",
    )
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    baseline_paths = tuple(args.baselines) if args.baselines else DEFAULT_BASELINES
    result = assess([load_yaml(path) for path in baseline_paths], load_yaml(args.evidence))
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["total"] != EXPECTED_TOTAL:
        print(
            f"ERRO: baseline esperada com {EXPECTED_TOTAL} obrigações; "
            f"encontrada(s) {result['total']} em {len(baseline_paths)} fonte(s)."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
