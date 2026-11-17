#!/usr/bin/env python3
"""Contrato nativo DEV de somente leitura, sem Docker ou operação em hosts.

A verificação HMAC é um *consumidor* de recibos que precisam ser emitidos por
validador externo independente. Nunca gera atestado em produção, não gerencia
segredos, não aplica labels e não autoriza dispatch por conta própria.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
LABEL = "reqsys-dev-native-runtime-v1"
REQUIRED_LABELS = (
    "self-hosted", "Windows", "X64", "reqsys-dev",
    "reqsys-dev-base-v1", LABEL,
)
REQUIRED_GATES = (
    "SESSION_LAUNCH_OK", "state_validated", "gateway_validated",
    "worktree_exclusive", "lease_exclusive", "native_dependencies_validated",
    "cost_zero_confirmed",
)
EXPECTED_TOOLS = ("git", "python", "node")
FORBIDDEN = ("docker", "compose", "container", "reboot", "deploy", "merge", "auto_merge", "gui_automation")


class NativeAdmissionBlocked(ValueError):
    """A checagem não autoriza um executor real."""


def _guard(condition: bool, error: str) -> None:
    if not condition:
        raise NativeAdmissionBlocked(error)


def validate_contract(policy: dict[str, Any]) -> dict[str, Any]:
    """Validação estática; nunca infere prontidão de manifesto ou labels."""
    _guard(type(policy) is dict, "policy_not_object")
    expected = {
        "schema_version": 1,
        "profile": "native_runtime",
        "environment": "dev",
        "profile_label": LABEL,
        "required_runner_labels": list(REQUIRED_LABELS),
        "required_tools": list(EXPECTED_TOOLS),
        "allowed_repository": "ericson-j-santos/reqsys-v2-enterprise-real",
        "receipt_issuer": "reqsys-governed-independent-validator-v1",
        "max_receipt_age_seconds": 300,
        "required_evidence": list(REQUIRED_GATES),
        "forbidden_execution": list(FORBIDDEN),
        "managed_labels_may_change": False,
        "dispatch_allowed": False,
        "requires_independent_receipt": True,
    }
    _guard(policy == expected, "native_policy_contract_invalid")
    return {"status": "policy_validated", "ready_for_work": False,
            "dispatch_allowed": False, "managed_labels_may_change": False,
            "profile_label": LABEL}


def _canonical_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def verify_independent_receipt(
    policy: dict[str, Any], receipt: dict[str, Any], *,
    verifier_key: bytes, expected_sha: str, expected_runner_instance_id: str,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Fail-closed; assinatura vinda de processo/credencial de outro domínio.

    Nunca assumir que um runner pode emitir seu próprio recibo. Os parâmetros
    de identidade e SHA vêm do controlador, não do documento não confiável.
    """
    validate_contract(policy)
    _guard(isinstance(receipt, dict), "receipt_not_object")
    _guard(isinstance(verifier_key, bytes) and len(verifier_key) >= 32, "verifier_key_unavailable")
    _guard(isinstance(expected_sha, str) and HEX40.fullmatch(expected_sha) is not None,
           "expected_sha_invalid")
    _guard(isinstance(expected_runner_instance_id, str)
           and re.fullmatch(r"reqsys-pc-[a-z0-9-]{8,40}", expected_runner_instance_id) is not None,
           "expected_runner_invalid")
    _guard(set(receipt) == {"payload", "signature"}, "receipt_envelope_invalid")
    payload = receipt["payload"]
    _guard(isinstance(payload, dict), "receipt_payload_invalid")
    signature = receipt["signature"]
    _guard(isinstance(signature, str) and re.fullmatch(r"[0-9a-f]{64}", signature) is not None,
           "signature_format_invalid")
    expected_signature = hmac.new(verifier_key, _canonical_bytes(payload), hashlib.sha256).hexdigest()
    _guard(hmac.compare_digest(expected_signature, signature), "receipt_signature_invalid")
    exact_fields = {
        "schema_version", "issuer", "issued_at", "repo", "source_sha", "environment",
        "profile", "profile_label", "runner_instance_id", "physical_host_id",
        "runner_status", "runner_busy", "runner_labels", "gates", "lease_id", "checkpoint_sha256",
    }
    _guard(set(payload) == exact_fields, "receipt_fields_invalid")
    _guard(payload["schema_version"] == 1 and
           payload["issuer"] == policy["receipt_issuer"], "receipt_issuer_invalid")
    _guard(payload["repo"] == policy["allowed_repository"] and
           payload["environment"] == "dev", "receipt_scope_invalid")
    _guard(payload["source_sha"] == expected_sha, "receipt_sha_mismatch")
    _guard(payload["profile"] == "native_runtime" and
           payload["profile_label"] == LABEL, "receipt_profile_invalid")
    _guard(payload["runner_instance_id"] == expected_runner_instance_id,
           "runner_identity_mismatch")
    _guard(isinstance(payload["physical_host_id"], str) and
           re.fullmatch(r"host-[a-z0-9-]{8,80}", payload["physical_host_id"]) is not None,
           "physical_host_id_invalid")
    _guard(payload["runner_labels"] == list(REQUIRED_LABELS), "runner_labels_invalid")
    _guard(payload["runner_status"] == "online" and payload["runner_busy"] is False,
           "runner_not_idle")
    _guard(isinstance(payload["lease_id"], str) and len(payload["lease_id"]) >= 16,
           "lease_unavailable")
    _guard(isinstance(payload["checkpoint_sha256"], str) and
           re.fullmatch(r"[0-9a-f]{64}", payload["checkpoint_sha256"]) is not None,
           "checkpoint_invalid")
    gates = payload["gates"]
    _guard(isinstance(gates, dict) and set(gates) == set(REQUIRED_GATES), "gates_invalid")
    _guard(all(gates[k] is True for k in REQUIRED_GATES), "required_gate_failed")
    try:
        timestamp = datetime.fromisoformat(payload["issued_at"])
    except (ValueError, TypeError):
        raise NativeAdmissionBlocked("receipt_timestamp_invalid") from None
    _guard(timestamp.tzinfo is not None, "receipt_timezone_missing")
    current = at if at is not None else datetime.now(timezone.utc)
    _guard(current.tzinfo is not None, "current_timezone_missing")
    seconds = (current - timestamp).total_seconds()
    _guard(0 <= seconds <= policy["max_receipt_age_seconds"], "receipt_expired_or_future")
    return {
        "status": "signed_receipt_validated",
        "source_sha": expected_sha,
        "runner_instance_id": expected_runner_instance_id,
        "profile_label": LABEL,
        "ready_for_work": True,
        # Recibo assinado não é autorização de dispatch nem de alterar labels.
        "dispatch_allowed": False,
        "managed_labels_may_change": False,
        "continuity_certified": False,
    }
