"""Pure eligibility rules for Teams notifications and incident recovery."""
from __future__ import annotations

import re
from typing import Any

SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
MATERIAL_NOOP_REASONS = frozenset(
    {
        "source_conclusion_skipped",
        "source_conclusion_cancelled",
        "no_material_remediation",
        "workflow_run_not_supported",
    }
)


def suppression_class(reason: str) -> str:
    return "material_noop" if reason in MATERIAL_NOOP_REASONS else "evidence_failure"


def delivery_result_decision(delivery_mode: str, result: Any) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "delivery_result_invalid"
    if result.get("dry_run", False) is not False or result.get("suppressed", False) is not False:
        return False, "delivery_not_real"
    status_code = result.get("status_code")
    if isinstance(status_code, bool) or not isinstance(status_code, int) or not 200 <= status_code < 300:
        return False, "delivery_http_invalid"
    if delivery_mode == "gateway":
        if result.get("entregue") is not True:
            return False, "gateway_delivery_unconfirmed"
        return True, "gateway_delivery_confirmed"
    if delivery_mode == "webhook_fallback":
        if result.get("success") is not True or result.get("route") != "webhook":
            return False, "webhook_delivery_unconfirmed"
        return True, "webhook_delivery_confirmed"
    return False, "delivery_mode_unknown"


def triage_decision(source_conclusion: str, evidence: Any) -> tuple[bool, str]:
    conclusion = str(source_conclusion or "").casefold()
    if conclusion != "success":
        return False, f"source_conclusion_{conclusion or 'unknown'}"
    if not isinstance(evidence, dict) or not evidence:
        return False, "triage_evidence_missing"
    pr = evidence.get("pr")
    triage = evidence.get("triage")
    analyzed_sha = str(evidence.get("analyzed_sha") or "")
    schema_version = str(evidence.get("schema_version") or "")
    run_id = evidence.get("run_id")
    result = str(evidence.get("result") or "").strip()
    if schema_version != "1.0.0":
        return False, "triage_evidence_schema_unknown"
    if not isinstance(run_id, int) or run_id <= 0:
        return False, "triage_evidence_run_invalid"
    if not isinstance(pr, dict) or not isinstance(pr.get("number"), int) or pr["number"] <= 0:
        return False, "triage_evidence_invalid_pr"
    if not isinstance(triage, dict) or not any(str(triage.get(key) or "").strip() for key in ("root_cause", "category")):
        return False, "triage_evidence_invalid_analysis"
    if not SHA40.fullmatch(analyzed_sha) or not result:
        return False, "triage_evidence_invalid_identity"
    pr_head_sha = str(pr.get("head_sha") or "")
    run_head_sha = str(pr.get("run_head_sha") or "")
    if (
        not SHA40.fullmatch(pr_head_sha)
        or not SHA40.fullmatch(run_head_sha)
        or analyzed_sha.casefold() != run_head_sha.casefold()
        or pr_head_sha.casefold() != run_head_sha.casefold()
        or pr.get("sha_current") is not True
    ):
        return False, "triage_evidence_sha_mismatch"
    return True, "material_triage"


def remediation_decision(report: Any) -> tuple[bool, str]:
    if not isinstance(report, dict):
        return False, "no_material_remediation"
    try:
        reruns = int(report.get("reruns_executed") or 0)
    except (TypeError, ValueError):
        return False, "invalid_remediation_evidence"
    if reruns <= 0:
        return False, "no_material_remediation"
    if not isinstance(report.get("target_pr_number"), int) or report["target_pr_number"] <= 0:
        return False, "invalid_remediation_pr"
    if not SHA40.fullmatch(str(report.get("target_head_sha") or "")):
        return False, "invalid_remediation_sha"
    return True, "material_remediation"


def workflow_run_delivery_decision(
    expected_run_id: int, expected_head_sha: str, jobs_payload: Any
) -> tuple[str, str]:
    if jobs_payload is None:
        return "observation_unavailable", "jobs_request_unavailable"
    if not isinstance(jobs_payload, dict) or not isinstance(jobs_payload.get("jobs"), list):
        return "observation_unavailable", "jobs_schema_invalid"
    if not isinstance(jobs_payload.get("total_count"), int):
        return "observation_unavailable", "jobs_schema_invalid"
    if jobs_payload["total_count"] != len(jobs_payload["jobs"]):
        return "observation_unavailable", "jobs_page_incomplete"
    matching = [job for job in jobs_payload["jobs"] if isinstance(job, dict) and job.get("name") == "Enviar commit ao Teams"]
    if len(matching) != 1:
        return "failure", "notification_job_missing_or_ambiguous"
    job = matching[0]
    if job.get("run_id") != expected_run_id or str(job.get("head_sha") or "").casefold() != expected_head_sha.casefold():
        return "observation_unavailable", "notification_job_identity_mismatch"
    steps = job.get("steps")
    if not isinstance(steps, list):
        return "observation_unavailable", "notification_steps_missing"
    conclusions = {
        str(step.get("name") or ""): str(step.get("conclusion") or "")
        for step in steps
        if isinstance(step, dict)
    }
    if conclusions.get("Confirmar entrega real") == "success":
        return "delivered", "real_delivery_confirmed"
    if conclusions.get("Confirmar supressão sem mudança material") == "success":
        return "suppressed", "material_notification_suppressed"
    return "failure", "real_delivery_not_confirmed"
