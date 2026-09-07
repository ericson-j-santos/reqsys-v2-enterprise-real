#!/usr/bin/env python3
"""Avalia a baseline normativa em modo de simulação sem fabricar conformidade."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

DEFAULT_BASELINE = Path("governance/bacen/normative/NORMATIVE-OBLIGATIONS-EXTENDED.yaml")
DEFAULT_EVIDENCE = Path("governance/bacen/normative/EVIDENCE-REGISTRY.yaml")


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


def assess(baseline: dict, evidence: dict) -> dict:
    obligations = baseline.get("obligations", []) or []
    refs = evidence_index(evidence)
    rows = []
    for obligation in obligations:
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
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = assess(load_yaml(args.baseline), load_yaml(args.evidence))
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if result["total"] != 57:
        print(f"ERRO: baseline esperada com 57 obrigações; encontrada(s) {result['total']}.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
