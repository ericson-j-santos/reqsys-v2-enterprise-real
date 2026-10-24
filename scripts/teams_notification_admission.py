"""Admissão fail-closed de notificações de workflows, sem rede ou segredos."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class AdmissionError(ValueError):
    """Evidência insuficiente ou incompatível; nenhuma entrega é admitida."""


ARTIFACTS = {
    "Ollama CI Triage": ("ollama-ci-triage-", "evidence.json"),
    "PR CI Remediation": ("pr-ci-remediation-evidence-", "report.json"),
}
NO_WORK_CONCLUSIONS = frozenset({"skipped", "cancelled", "neutral"})
TRIAGE_RESULTS = frozenset({
    "OLLAMA_CI_TRIAGE_OK",
    "OLLAMA_CI_TRIAGE_DEGRADED",
    "OLLAMA_CI_TRIAGE_BLOCKED",
})


def positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def classify_workflow_run(
    source: dict[str, Any],
    load_artifact: Callable[[int, str, str], Any],
) -> tuple[bool, str, dict[str, Any]]:
    """Classifica antes do locator; conclusões sem trabalho nem baixam artifacts.

    O run_id de evidence.json identifica o CI analisado, não o run de triagem.
    O vínculo ao run produtor é preservado pelo callback com source.id.
    """
    if not isinstance(source, dict):
        raise AdmissionError("workflow_source_invalid")
    name = source.get("name")
    if name not in ARTIFACTS:
        return False, "workflow_run_not_supported", {}
    conclusion = source.get("conclusion")
    if conclusion in NO_WORK_CONCLUSIONS:
        return False, "source_without_execution", {}
    if conclusion not in {"success", "failure", "timed_out"}:
        raise AdmissionError("source_conclusion_unverified")
    run_id = source.get("id")
    if not positive_integer(run_id):
        raise AdmissionError("source_run_id_invalid")
    prefix, filename = ARTIFACTS[name]
    payload = load_artifact(run_id, prefix, filename)
    if not isinstance(payload, dict) or payload.get("schema_version") != "1.0.0":
        raise AdmissionError("source_evidence_missing_or_invalid")

    if name == "PR CI Remediation":
        reruns = payload.get("reruns_executed")
        if isinstance(reruns, bool) or not isinstance(reruns, int) or reruns < 0:
            raise AdmissionError("remediation_counter_invalid")
        if reruns == 0:
            return False, "no_material_remediation", {}
        if payload.get("execute") is not True:
            raise AdmissionError("remediation_effect_unverified")
        return True, "material_remediation", payload

    result = payload.get("result")
    if result not in TRIAGE_RESULTS or not positive_integer(payload.get("run_id")):
        raise AdmissionError("triage_result_unverified")
    triage = payload.get("triage", {})
    if not isinstance(triage, dict):
        raise AdmissionError("triage_payload_invalid")
    if result == "OLLAMA_CI_TRIAGE_OK":
        category = triage.get("category")
        if not isinstance(category, str) or category not in {
            "code", "test", "config", "dependency", "security",
            "governance", "transient", "unknown",
        }:
            raise AdmissionError("triage_category_missing")
    else:
        reason = triage.get("root_cause") or payload.get("reason") or payload.get("degraded_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise AdmissionError("triage_execution_evidence_missing")
    return True, "executed_triage", payload
