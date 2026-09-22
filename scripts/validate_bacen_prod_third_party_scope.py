#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ALLOWED = {"USED_IN_PROD", "NOT_USED_IN_PROD", "UNVERIFIED"}
REPO_ROOT = Path(__file__).resolve().parents[1]


def _validate_reference(reference: object, repo_root: Path) -> tuple[bool, bool, str]:
    value = str(reference or "").strip()
    if not value:
        return False, False, "empty_reference"

    if value.startswith(("https://", "http://")):
        return True, False, "external_reference"

    if Path(value).is_absolute():
        return False, False, "absolute_path_not_allowed"

    root = repo_root.resolve()
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False, False, "path_outside_repository"

    if not candidate.exists():
        return False, False, "path_not_found"

    return True, True, "local_path_verified"


def validate(path: Path, *, repo_root: Path = REPO_ROOT) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    vendors = data.get("vendors") or []
    seen: set[str] = set()
    evidence_reference_errors: list[dict[str, str]] = []
    local_evidence_verified_vendor_ids: list[str] = []

    if data.get("control_id") != "BACEN-05":
        errors.append("control_id must be BACEN-05")
    if data.get("scope") != "prod":
        errors.append("scope must be prod")
    if data.get("mode") != "fail_safe":
        errors.append("mode must be fail_safe")
    if not vendors:
        errors.append("vendors must not be empty")

    for vendor in vendors:
        vendor_id = str(vendor.get("id") or "").strip()
        classification = vendor.get("classification")
        evidence = vendor.get("evidence") or []
        if not vendor_id:
            errors.append("vendor without id")
            continue
        if vendor_id in seen:
            errors.append(f"duplicate vendor id: {vendor_id}")
        seen.add(vendor_id)
        if classification not in ALLOWED:
            errors.append(f"{vendor_id}: invalid classification {classification!r}")
        if classification == "USED_IN_PROD" and not evidence:
            errors.append(f"{vendor_id}: USED_IN_PROD requires evidence")
        if classification == "NOT_USED_IN_PROD" and not evidence:
            errors.append(f"{vendor_id}: NOT_USED_IN_PROD requires explicit evidence")

        refs_valid = True
        refs_all_local = bool(evidence)
        for reference in evidence:
            valid, locally_verified, detail = _validate_reference(reference, repo_root)
            refs_valid = refs_valid and valid
            refs_all_local = refs_all_local and locally_verified
            if not valid:
                evidence_reference_errors.append(
                    {
                        "vendor_id": vendor_id,
                        "reference": str(reference),
                        "reason": detail,
                    }
                )
                errors.append(f"{vendor_id}: invalid evidence reference {reference!r} ({detail})")

        if (
            classification in {"USED_IN_PROD", "NOT_USED_IN_PROD"}
            and evidence
            and refs_valid
            and refs_all_local
        ):
            local_evidence_verified_vendor_ids.append(vendor_id)

    fly = next((v for v in vendors if v.get("name") == "Fly.io"), None)
    if not fly or fly.get("classification") != "USED_IN_PROD":
        errors.append("Fly.io must be explicitly recorded as USED_IN_PROD")

    unverified_vendor_ids = [
        str(v.get("id"))
        for v in vendors
        if v.get("classification") == "UNVERIFIED"
    ]

    return {
        "ok": not errors,
        "errors": errors,
        "vendor_count": len(vendors),
        "counts": {k: sum(1 for v in vendors if v.get("classification") == k) for k in sorted(ALLOWED)},
        "local_evidence_verified_vendor_ids": sorted(local_evidence_verified_vendor_ids),
        "unverified_vendor_ids": sorted(unverified_vendor_ids),
        "remaining_unverified_count": len(unverified_vendor_ids),
        "evidence_reference_errors": evidence_reference_errors,
        "production_touched": False,
        "status_promotion_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="governance/bacen/PROD-THIRD-PARTY-SCOPE.yaml")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = validate(Path(args.input))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
