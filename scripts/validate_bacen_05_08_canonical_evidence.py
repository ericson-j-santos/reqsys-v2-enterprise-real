#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

import yaml

EXPECTED_PROVIDER_DOMAINS = {
    "T01": {"microsoft.com"},
    "T06": {"github.com"},
    "T14": {"fly.io", "www.fly.io"},
}


def _host_allowed(url: str, allowed: set[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(host == domain or host.endswith("." + domain) for domain in allowed)


def validate(third_party_path: Path, executive_path: Path) -> dict:
    errors: list[str] = []
    third = yaml.safe_load(third_party_path.read_text(encoding="utf-8")) or {}
    executive = yaml.safe_load(executive_path.read_text(encoding="utf-8")) or {}

    if third.get("control_id") != "BACEN-05":
        errors.append("third_party control_id must be BACEN-05")
    if third.get("scope") != "prod":
        errors.append("third_party scope must be prod")
    if third.get("status_promotion_allowed") is not False:
        errors.append("BACEN-05 status promotion must remain disabled")
    if third.get("production_touched") is not False:
        errors.append("BACEN-05 production_touched must remain false")

    providers = third.get("providers") or []
    ids = [str(item.get("id") or "") for item in providers]
    if set(ids) != set(EXPECTED_PROVIDER_DOMAINS):
        errors.append("documentary registry must contain exactly T01, T06 and T14")
    if len(ids) != len(set(ids)):
        errors.append("duplicate provider id")

    for provider in providers:
        provider_id = str(provider.get("id") or "")
        if provider.get("classification_observed") != "USED_IN_PROD":
            errors.append(f"{provider_id}: classification_observed must remain USED_IN_PROD")

        documents = provider.get("official_documents") or []
        if not documents:
            errors.append(f"{provider_id}: official_documents required")
        for document in documents:
            source_url = str(document.get("source_url") or "")
            if not _host_allowed(source_url, EXPECTED_PROVIDER_DOMAINS.get(provider_id, set())):
                errors.append(f"{provider_id}: official source must use expected HTTPS domain")
            if document.get("source_status") != "verified_official_public":
                errors.append(f"{provider_id}: source_status must be verified_official_public")

        legal = provider.get("legal_review") or {}
        status = legal.get("status")
        signoff_reference = legal.get("signoff_reference")
        if status == "approved" and not signoff_reference:
            errors.append(f"{provider_id}: approved legal review requires signoff_reference")
        if status != "approved" and signoff_reference:
            errors.append(f"{provider_id}: pending legal review cannot carry signoff_reference")

        if provider_id == "T14":
            dpa = next(
                (doc for doc in documents if doc.get("type") == "data_processing_agreement_request"),
                None,
            )
            if not dpa:
                errors.append("T14: DPA request evidence required")
            else:
                if dpa.get("customer_signature_required") is not True:
                    errors.append("T14: customer_signature_required must be true")
                activation = dpa.get("contract_activation_status")
                signature_ref = dpa.get("customer_signature_reference")
                if activation == "active" and not signature_ref:
                    errors.append("T14: active DPA requires customer_signature_reference")
                if activation != "active" and signature_ref:
                    errors.append("T14: inactive DPA cannot carry customer_signature_reference")

    if executive.get("control_id") != "BACEN-08":
        errors.append("executive control_id must be BACEN-08")
    if executive.get("control_status") != "partial":
        errors.append("BACEN-08 control_status must remain partial")
    if executive.get("automatic_status_promotion_allowed") is not False:
        errors.append("BACEN-08 automatic status promotion must remain disabled")
    if executive.get("production_touched") is not False:
        errors.append("BACEN-08 production_touched must remain false")

    authenticated = executive.get("authenticated_evidence") or {}
    if authenticated.get("structural_status") != "structurally_valid":
        errors.append("BACEN-08 authenticated evidence must be structurally valid")
    if len(str(authenticated.get("comment_sha256") or "")) != 64:
        errors.append("BACEN-08 authenticated evidence hash must have 64 chars")

    formal = executive.get("formal_designation") or {}
    if formal.get("status") != "pending_human_formal_signoff":
        errors.append("BACEN-08 formal designation must remain pending human signoff")
    for field in ("institutional_document_reference", "signed_by_reference", "signed_at"):
        if formal.get(field) is not None:
            errors.append(f"BACEN-08 formal designation {field} must remain null before signoff")
    if formal.get("automation_may_infer_approval") is not False:
        errors.append("BACEN-08 automation_may_infer_approval must be false")

    report = executive.get("annual_report") or {}
    if report.get("status") != "draft_pending_human_formal_signoff":
        errors.append("BACEN-08 annual report must remain draft pending human signoff")
    for field in ("signoff_reference", "signed_by_reference", "signed_at"):
        if report.get(field) is not None:
            errors.append(f"BACEN-08 annual report {field} must remain null before signoff")
    if report.get("automation_may_infer_approval") is not False:
        errors.append("BACEN-08 report automation_may_infer_approval must be false")

    blockers = set(executive.get("remaining_formal_blockers") or [])
    expected_blockers = {"formal_executive_designation", "annual_report_formal_signoff"}
    if blockers != expected_blockers:
        errors.append("BACEN-08 remaining_formal_blockers must preserve both formal blockers")

    return {
        "ok": not errors,
        "errors": errors,
        "bacen_05_documented_provider_ids": sorted(ids),
        "bacen_05_legal_signoff_complete": all(
            (provider.get("legal_review") or {}).get("status") == "approved"
            for provider in providers
        ),
        "bacen_08_formal_designation_complete": formal.get("status") == "approved",
        "bacen_08_annual_report_signoff_complete": report.get("status") == "formally_signed",
        "control_statuses": {"BACEN-05": "partial", "BACEN-08": "partial"},
        "production_touched": False,
        "status_promotion_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--third-party",
        default="governance/bacen/PROD-THIRD-PARTY-DOCUMENTARY-EVIDENCE.yaml",
    )
    parser.add_argument(
        "--executive",
        default="governance/bacen/BACEN-08-FORMALIZATION-PACKET.yaml",
    )
    parser.add_argument("--output")
    args = parser.parse_args()
    result = validate(Path(args.third_party), Path(args.executive))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
