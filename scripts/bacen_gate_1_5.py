#!/usr/bin/env python3
"""Gate 1.5 BACEN: compara base e head usando o mesmo ``as_of``.

O gate reutiliza a derivação canônica de status. O relógio é congelado uma vez
por execução: varia o código/dado entre base e head, nunca o instante temporal.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.bacen_derived_status import derive_status, parse_utc

NORMATIVE_FILES = (
    Path("governance/bacen/normative/NORMATIVE-BASELINE.yaml"),
    Path("governance/bacen/normative/NORMATIVE-OBLIGATIONS-EXTENDED.yaml"),
)

STATUS_RANK = {
    "nao_avaliado": 0,
    "lacuna": 1,
    "parcial": 2,
    "implementado": 3,
    "evidenciado": 4,
}


@dataclass(frozen=True)
class Snapshot:
    obligations: dict[str, dict[str, Any]]
    evidences: tuple[dict[str, Any], ...]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"arquivo normativo ausente: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"YAML inválido: {path}")
    return payload


def load_snapshot(root: Path) -> Snapshot:
    obligations: dict[str, dict[str, Any]] = {}
    evidences: list[dict[str, Any]] = []

    for relative in NORMATIVE_FILES:
        payload = _read_yaml(root / relative)
        file_obligations = payload.get("obligations") or []
        if not isinstance(file_obligations, list):
            raise ValueError(f"obligations deve ser lista: {relative}")

        for obligation in file_obligations:
            if not isinstance(obligation, dict):
                raise ValueError(f"obrigação inválida em {relative}")
            uid = obligation.get("uid")
            if not uid:
                raise ValueError(f"obrigação sem uid em {relative}")
            if uid in obligations:
                raise ValueError(f"uid normativo duplicado: {uid}")
            if "status" in obligation:
                raise ValueError(f"status manual proibido em {uid}")
            obligations[str(uid)] = obligation

            inline_evidences = obligation.get("evidences") or []
            if not isinstance(inline_evidences, list):
                raise ValueError(f"evidences deve ser lista em {uid}")
            evidences.extend(inline_evidences)

        top_evidences = payload.get("evidences") or []
        if not isinstance(top_evidences, list):
            raise ValueError(f"evidences deve ser lista: {relative}")
        evidences.extend(top_evidences)

    return Snapshot(obligations=obligations, evidences=tuple(evidences))


def derive_snapshot(snapshot: Snapshot, *, as_of: str) -> dict[str, str]:
    parse_utc(as_of)
    result: dict[str, str] = {}
    for uid, obligation in snapshot.obligations.items():
        result[uid] = derive_status(
            obligation=obligation,
            as_of=as_of,
            assessment=obligation.get("assessment"),
            applicability_decision=obligation.get("applicability_decision"),
            evidences=snapshot.evidences,
        )
    return result


def _transition_is_regression(base_status: str, head_status: str) -> tuple[bool, str | None]:
    if base_status == head_status:
        return False, None

    if "nao_aplicavel" in (base_status, head_status):
        return True, "transicao_nao_aplicavel_exige_revisao_explicita"

    if base_status not in STATUS_RANK or head_status not in STATUS_RANK:
        return True, "status_fora_da_ordem_governada"

    if STATUS_RANK[head_status] < STATUS_RANK[base_status]:
        return True, "regressao_de_status_derivado"

    return False, None


def compare_snapshots(*, base_root: Path, head_root: Path, as_of: str) -> dict[str, Any]:
    """Compara dois snapshots no mesmo instante temporal obrigatório."""
    parse_utc(as_of)
    base = load_snapshot(base_root)
    head = load_snapshot(head_root)
    base_statuses = derive_snapshot(base, as_of=as_of)
    head_statuses = derive_snapshot(head, as_of=as_of)

    regressions: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []

    for uid, base_obligation in sorted(base.obligations.items()):
        head_obligation = head.obligations.get(uid)
        if head_obligation is None:
            regressions.append(
                {
                    "uid": uid,
                    "code": base_obligation.get("code"),
                    "reason": "obrigacao_removida",
                    "base_status": base_statuses[uid],
                    "head_status": None,
                }
            )
            continue

        if base_obligation.get("code") != head_obligation.get("code"):
            regressions.append(
                {
                    "uid": uid,
                    "code": base_obligation.get("code"),
                    "head_code": head_obligation.get("code"),
                    "reason": "identidade_legivel_alterada",
                    "base_status": base_statuses[uid],
                    "head_status": head_statuses[uid],
                }
            )
            continue

        base_status = base_statuses[uid]
        head_status = head_statuses[uid]
        is_regression, reason = _transition_is_regression(base_status, head_status)
        transition = {
            "uid": uid,
            "code": base_obligation.get("code"),
            "base_status": base_status,
            "head_status": head_status,
            "changed": base_status != head_status,
        }
        transitions.append(transition)
        if is_regression:
            regressions.append({**transition, "reason": reason})

    new_uids = sorted(set(head.obligations) - set(base.obligations))
    result = {
        "schema_version": "1.0.0",
        "gate": "BACEN-1.5",
        "mode": "fail_closed",
        "as_of": as_of,
        "same_as_of_for_base_and_head": True,
        "base_obligations": len(base.obligations),
        "head_obligations": len(head.obligations),
        "new_obligations": new_uids,
        "regression_count": len(regressions),
        "regressions": regressions,
        "transitions": transitions,
        "decision": "blocked" if regressions else "pass",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--head-root", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="UTC ISO-8601 congelado e compartilhado entre base/head")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = compare_snapshots(base_root=args.base_root, head_root=args.head_root, as_of=args.as_of)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if result["decision"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
