#!/usr/bin/env python3
"""Emissor governado de recibos nativos: somente domínio de confiança externo.

Nunca conecta ou executa no host. Só assina após testemunho AUTENTICADO
por chave distinta do emissor, readback oficial do GitHub, auditoria e CAS.
É uma biblioteca, não um dispatch ou certificado de continuidade E2E.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

from scripts.reqsys_native_gateway_preflight import (
    ISSUER, ALLOWED_REPO, COMMAND_TAG, verify_gateway_source,
)
from scripts.reqsys_native_github_readback import readback, GitHubReadbackBlocked
from scripts.validate_reqsys_native_dev_profile import (
    NativeAdmissionBlocked, REQUIRED_GATES, _canonical_bytes, validate_contract,
)

WITNESS_ISSUER = "reqsys-external-gateway-audit-authority-v1"
WITNESS_SOURCE = "trusted-independent-command-gateway-audit-v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
IDENTITY = re.compile(r"reqsys-pc-[a-z0-9-]{8,40}\Z")
HOST_ID = re.compile(r"host-[a-z0-9-]{8,80}\Z")
WITNESS_FIELDS = frozenset({
    "schema_version", "issuer", "source", "issued_at", "event_id", "repo", "source_sha",
    "run_id", "job_id", "runner_id", "runner_instance_id", "physical_host_id",
    "session_id", "correlation_id", "lease_id", "checkpoint_sha256", "gates",
    "launcher_sha256", "gateway_audit_sha256", "checkpoint_readback_sha256",
})
AUDIT_FIELDS = frozenset({
    "schema_version", "source", "event_id", "source_sha", "session_id",
    "correlation_id", "command_tag", "result", "gateway_exit_code", "state_changed",
})
CHECKPOINT_FIELDS = frozenset({
    "schema_version", "source", "event_id", "source_sha", "physical_host_id",
    "lease_id", "checkpoint_sha256", "lease_exclusive", "state_validated",
})


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise NativeAdmissionBlocked(code)


def _digest(value: dict[str, Any]) -> str:
    try:
        return hashlib.sha256(_canonical_bytes(value)).hexdigest()
    except (ValueError, TypeError, OverflowError):
        raise NativeAdmissionBlocked("unserializable_evidence") from None


def _timestamp(value: Any, current: datetime, ttl: int) -> None:
    try:
        timestamp = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        raise NativeAdmissionBlocked("witness_time_invalid") from None
    _require(timestamp.tzinfo is not None and current.tzinfo is not None and
             0 <= (current - timestamp).total_seconds() <= ttl,
             "witness_stale_or_future")


def _verify_witness(witness: dict[str, Any], *, key: bytes,
                    current: datetime, ttl: int) -> dict[str, Any]:
    _require(isinstance(witness, dict) and set(witness) == {"payload", "signature"},
             "witness_envelope_invalid")
    p = witness.get("payload")
    sig = witness.get("signature")
    _require(isinstance(p, dict) and set(p) == WITNESS_FIELDS,
             "witness_fields_invalid")
    _require(isinstance(sig, str) and re.fullmatch(r"[0-9a-f]{64}", sig) is not None,
             "witness_signature_format_invalid")
    _require(hmac.compare_digest(sig, hmac.new(key, _canonical_bytes(p),
                                      hashlib.sha256).hexdigest()),
             "witness_signature_invalid")
    _require(p["schema_version"] == 1 and p["issuer"] == WITNESS_ISSUER and
             p["source"] == WITNESS_SOURCE and p["repo"] == ALLOWED_REPO,
             "witness_issuer_invalid")
    _timestamp(p["issued_at"], current, ttl)
    _require(isinstance(p["event_id"], str) and
             re.fullmatch(r"native-[a-z0-9-]{14,90}", p["event_id"]) is not None,
             "witness_event_id_invalid")
    _require(all(type(p[k]) is int and p[k] > 0 for k in ("run_id", "job_id", "runner_id")),
             "witness_api_ids_invalid")
    _require(isinstance(p["source_sha"], str) and SHA40.fullmatch(p["source_sha"]) is not None,
             "witness_sha_invalid")
    _require(isinstance(p["runner_instance_id"], str) and
             IDENTITY.fullmatch(p["runner_instance_id"]) is not None and
             isinstance(p["physical_host_id"], str) and
             HOST_ID.fullmatch(p["physical_host_id"]) is not None,
             "witness_identity_invalid")
    _require(all(isinstance(p[k], str) and len(p[k]) >= 12
                 for k in ("session_id", "correlation_id", "lease_id")),
             "witness_session_invalid")
    _require(all(isinstance(p[k], str) and SHA64.fullmatch(p[k]) is not None
                 for k in ("checkpoint_sha256", "launcher_sha256",
                           "gateway_audit_sha256", "checkpoint_readback_sha256")),
             "witness_digests_invalid")
    _require(isinstance(p["gates"], dict) and set(p["gates"]) == set(REQUIRED_GATES) and
             all(p["gates"][k] is True for k in REQUIRED_GATES),
             "witness_gates_not_proven")
    return p


def issue_independent_receipt(
    policy: dict[str, Any], launcher: dict[str, Any], gateway: dict[str, Any],
    audit_event: dict[str, Any], checkpoint_readback: dict[str, Any],
    witness: dict[str, Any], *, witness_verifier_key: bytes, issuer_signing_key: bytes,
    github_read_token: str, expected_sha: str, expected_runner_instance_id: str,
    expected_run_id: int, expected_job_id: int, expected_runner_id: int,
    execution_context: dict[str, str],
    fetch: Callable[..., dict[str, Any]] | None = None,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Emite recibo em memória APENAS com confiança externa + leitura GitHub.

    O produtor de witness pertence a outro domínio de custódia e tem de observar
    audit log ORIGINAL do Gateway, nunca somente campos fornecidos pelo runner.
    Até sua implantação real, a operação real permanecerá BLOQUEADA.
    """
    validate_contract(policy)
    _require(isinstance(execution_context, dict) and
             execution_context.get("GITHUB_ACTIONS") == "true" and
             execution_context.get("RUNNER_ENVIRONMENT") == "github-hosted" and
             execution_context.get("GITHUB_REPOSITORY") == ALLOWED_REPO and
             execution_context.get("GITHUB_SHA") == expected_sha,
             "independent_execution_context_required")
    _require(isinstance(witness_verifier_key, bytes) and len(witness_verifier_key) >= 32 and
             isinstance(issuer_signing_key, bytes) and len(issuer_signing_key) >= 32 and
             not hmac.compare_digest(witness_verifier_key, issuer_signing_key),
             "independent_key_custody_invalid")
    _require(isinstance(expected_sha, str) and SHA40.fullmatch(expected_sha) is not None and
             isinstance(expected_runner_instance_id, str) and
             IDENTITY.fullmatch(expected_runner_instance_id) is not None,
             "expected_identity_invalid")
    current = at or datetime.now(timezone.utc)
    _require(current.tzinfo is not None, "current_time_invalid")
    w = _verify_witness(witness, key=witness_verifier_key,
                        current=current, ttl=policy["max_receipt_age_seconds"])
    _require((w["source_sha"], w["runner_instance_id"], w["run_id"], w["job_id"],
              w["runner_id"]) == (expected_sha, expected_runner_instance_id,
                                   expected_run_id, expected_job_id, expected_runner_id),
             "witness_target_mismatch")
    _require(isinstance(launcher, dict) and _digest(launcher) == w["launcher_sha256"],
             "launcher_origin_mismatch")
    _require(isinstance(audit_event, dict) and set(audit_event) == AUDIT_FIELDS and
             _digest(audit_event) == w["gateway_audit_sha256"],
             "gateway_audit_origin_mismatch")
    _require(isinstance(checkpoint_readback, dict) and
             set(checkpoint_readback) == CHECKPOINT_FIELDS and
             _digest(checkpoint_readback) == w["checkpoint_readback_sha256"],
             "checkpoint_source_mismatch")
    _require(checkpoint_readback == {
        "schema_version": 1, "source": "trusted-independent-cas-readback-v1",
        "event_id": w["event_id"], "source_sha": expected_sha,
        "physical_host_id": w["physical_host_id"], "lease_id": w["lease_id"],
        "checkpoint_sha256": w["checkpoint_sha256"],
        "lease_exclusive": True, "state_validated": True,
    }, "independent_checkpoint_invalid")
    _require(audit_event == {
        "schema_version": 1, "source": "trusted-independent-command-gateway-audit-v1",
        "event_id": w["event_id"], "source_sha": expected_sha,
        "session_id": w["session_id"], "correlation_id": w["correlation_id"],
        "command_tag": COMMAND_TAG, "result": "ok", "gateway_exit_code": 0,
        "state_changed": False,
    }, "independent_gateway_audit_invalid")
    _require(isinstance(gateway, dict) and gateway.get("session_id") == w["session_id"]
             and gateway.get("correlation_id") == w["correlation_id"]
             and gateway.get("result") == "ok" and gateway.get("gateway_exit_code") == 0
             and gateway.get("state_changed") is False
             and gateway.get("command_tag") == COMMAND_TAG
             and gateway.get("head") == expected_sha,
             "gateway_transcript_mismatch")
    _require(isinstance(launcher, dict) and launcher.get("host") == w["physical_host_id"]
             and launcher.get("session_id") == w["session_id"]
             and launcher.get("head") == expected_sha
             and launcher.get("result") == "SESSION_LAUNCH_OK"
             and launcher.get("state_validated") is True,
             "launcher_transcript_mismatch")
    try:
        args = dict(run_id=expected_run_id, job_id=expected_job_id,
                    runner_id=expected_runner_id, expected_sha=expected_sha,
                    expected_labels=policy["required_runner_labels"],
                    token=github_read_token, at=current)
        if fetch is not None:
            args["fetch"] = fetch
        observed = readback(**args)
    except GitHubReadbackBlocked as exc:
        raise NativeAdmissionBlocked(str(exc)) from None
    _require(observed["source"] == "github_rest_independent_readback" and
             observed["source_sha"] == expected_sha and
             observed["identity_binding_verified"] is False and
             observed["runner_status"] == "online" and
             observed["runner_busy"] is False,
             "independent_github_unverified")
    bundle = {"schema_version": 1, "launcher": launcher, "gateway": gateway,
              "github": {
                  "source": observed["source"], "run_id": observed["run_id"],
                  "runner_instance_id": expected_runner_instance_id,
                  "physical_host_id": w["physical_host_id"],
                  "status": observed["runner_status"], "busy": observed["runner_busy"],
                  # GitHub API checked exact label set; preserve contractual ordering.
                  "labels": list(policy["required_runner_labels"]),
                  "head_sha": observed["source_sha"],
                  "observed_at": observed["observed_at"],
              }}
    receipt_payload = {
        "schema_version": 1, "issuer": ISSUER, "issued_at": w["issued_at"],
        "repo": ALLOWED_REPO, "source_sha": expected_sha,
        "environment": "dev", "profile": "native_runtime",
        "profile_label": policy["profile_label"],
        "runner_instance_id": expected_runner_instance_id,
        "physical_host_id": w["physical_host_id"],
        "runner_status": "online", "runner_busy": False,
        "runner_labels": list(policy["required_runner_labels"]),
        "gates": w["gates"], "lease_id": w["lease_id"],
        "checkpoint_sha256": w["checkpoint_sha256"],
    }
    receipt = {"payload": receipt_payload,
               "signature": hmac.new(issuer_signing_key, _canonical_bytes(receipt_payload),
                                     hashlib.sha256).hexdigest()}
    claim_payload = {
        "schema_version": 1, "issuer": ISSUER, "issued_at": w["issued_at"],
        "source_sha": expected_sha, "runner_instance_id": expected_runner_instance_id,
        "bundle_sha256": _digest(bundle), "receipt_sha256": _digest(receipt),
    }
    attestation = {"payload": claim_payload,
                   "signature": hmac.new(issuer_signing_key, _canonical_bytes(claim_payload),
                                         hashlib.sha256).hexdigest()}
    verified = verify_gateway_source(
        policy, bundle, receipt, attestation, verifier_key=issuer_signing_key,
        expected_sha=expected_sha,
        expected_runner_instance_id=expected_runner_instance_id,
        expected_github_run_id=expected_run_id, at=current,
    )
    _require(verified["status"] == "INDEPENDENT_GATEWAY_BINDING_VALIDATED" and
             verified["dispatch_allowed"] is False and
             verified["ready_for_work"] is False and
             verified["continuity_certified"] is False,
             "emitted_receipt_not_safe")
    return {"status": "INDEPENDENT_RECEIPT_EMITTED", "event_id": w["event_id"],
            "bundle": bundle, "receipt": receipt, "attestation": attestation,
            "verification": verified, "ready_for_work": False,
            "dispatch_allowed": False, "continuity_certified": False,
            "source_sha": expected_sha}


def main(argv: list[str] | None = None) -> int:
    """Entrada governada para job GitHub-hosted, sem execução em computador.

    Valores esperados de host/run vêm do controlador autorizado do job, nunca
    do payload. Nunca imprime chave, token, recibo ou atestado no stdout.
    """
    import argparse
    import os
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Emissor independente, sem dispatch")
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--runner-instance-id", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--runner-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _require(args.output.is_absolute(), "output_must_be_absolute")
        _require(not args.output.exists() and not args.output.is_symlink(),
                 "output_already_exists")
        # Evitar input redirecionado para segredos ou arquivos mutáveis de host.
        def load(path: Path) -> dict[str, Any]:
            _require(path.is_absolute() and path.is_file() and not path.is_symlink() and
                     0 < path.stat().st_size < 65536, "evidence_file_invalid")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError):
                raise NativeAdmissionBlocked("evidence_json_invalid") from None
            _require(isinstance(value, dict), "evidence_json_invalid")
            return value
        policy = load(args.policy)
        data = load(args.evidence)
        _require(set(data) == {"launcher", "gateway", "gateway_audit", "checkpoint_readback",
                               "witness"}, "evidence_envelope_invalid")
        witness_key = os.environ.get("REQSYS_NATIVE_GATEWAY_WITNESS_KEY", "").encode()
        signing_key = os.environ.get("REQSYS_NATIVE_VALIDATOR_KEY", "").encode()
        token = os.environ.get("REQSYS_NATIVE_GITHUB_READ_TOKEN", "")
        result = issue_independent_receipt(
            policy, data["launcher"], data["gateway"], data["gateway_audit"],
            data["checkpoint_readback"], data["witness"],
            witness_verifier_key=witness_key, issuer_signing_key=signing_key,
            github_read_token=token, expected_sha=args.expected_sha,
            expected_runner_instance_id=args.runner_instance_id,
            expected_run_id=args.run_id, expected_job_id=args.job_id,
            expected_runner_id=args.runner_id, execution_context=dict(os.environ),
        )
        # Arquivo de prova com assinatura, nunca segredo. Arquivo novo exclusivo.
        _require(args.output.parent.is_dir() and not args.output.parent.is_symlink(),
                 "output_dir_invalid")
        mode = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        mode |= getattr(os, "O_NOFOLLOW", 0)
        serialized = _canonical_bytes(result)
        _require(len(serialized) <= 65536, "receipt_oversized")
        fd = os.open(args.output, mode, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=True) as output:
                output.write(serialized + b"\n")
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            args.output.unlink(missing_ok=True)
            raise
        print(json.dumps({"status": "INDEPENDENT_RECEIPT_EMITTED",
                          "event_id": result["event_id"],
                          "receipt_sha256": hashlib.sha256(serialized).hexdigest(),
                          "ready_for_work": False, "dispatch_allowed": False,
                          "continuity_certified": False}, sort_keys=True))
        return 0
    except (NativeAdmissionBlocked, OSError) as exc:
        code = str(exc) if isinstance(exc, NativeAdmissionBlocked) else "io_blocked"
        print(json.dumps({"status": "BLOCKED_INDEPENDENT_ISSUER", "reason_code": code,
                          "ready_for_work": False, "dispatch_allowed": False,
                          "continuity_certified": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
