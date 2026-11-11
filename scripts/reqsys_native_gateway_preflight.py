#!/usr/bin/env python3
"""Pré-admissão DEV nativa: candidato local + validação externa sem despacho.

A origem física é o Session Launcher + Command Gateway existentes. Este
consumidor NÃO implementa/emite recibos no host: exige atestado independente
externo que vincule leitura do Gateway e inventário oficial GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.validate_reqsys_native_dev_profile import (
    NativeAdmissionBlocked,
    _canonical_bytes,
    validate_contract,
    verify_independent_receipt,
)

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
INSTANCE = re.compile(r"reqsys-pc-[a-z0-9-]{8,40}\Z")
ALLOWED_REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
ISSUER = "reqsys-governed-independent-validator-v1"
COMMAND_TAG = "reqsys-native-dev-readonly-probe"
MANIFEST_KEYS = {
    "schema_version", "profile", "environment", "runner_instance_id",
    "source_sha", "runtime_root", "runner_labels", "capabilities",
    "allowed_environments", "safeguards",
}
BUNDLE_KEYS = {"schema_version", "launcher", "gateway", "github"}
ATTESTATION_KEYS = {"schema_version", "issuer", "issued_at", "source_sha",
                    "runner_instance_id", "bundle_sha256", "receipt_sha256"}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise NativeAdmissionBlocked(reason)


def _no_reparse(path: Path) -> bool:
    p = path
    while True:
        try:
            st = p.lstat()
            if p.is_symlink() or bool(getattr(st, "st_file_attributes", 0) &
                                      getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
                return False
        except OSError:
            return False
        if p == p.parent:
            return True
        p = p.parent


def local_preflight(policy: dict[str, Any], manifest: dict[str, Any], *,
                    expected_sha: str, expected_runner_instance_id: str, root: Path, os_name: str,
                    architecture: str, which: Callable[[str], str | None] = shutil.which,
                    ) -> dict[str, Any]:
    """Só qualifica candidato: nunca diz ready_for_work nem habilita dispatch."""
    validate_contract(policy)
    require(os_name == "nt" and architecture.casefold() in {"amd64", "x86_64"},
            "windows_x64_required")
    require(isinstance(expected_sha, str) and bool(SHA40.fullmatch(expected_sha)),
            "expected_sha_invalid")
    require(isinstance(manifest, dict) and set(manifest) == MANIFEST_KEYS,
            "manifest_contract_invalid")
    require(manifest["schema_version"] == 1 and manifest["profile"] == "native_runtime"
            and manifest["environment"] == "dev"
            and manifest["allowed_environments"] == ["dev"], "manifest_scope_invalid")
    require(manifest["source_sha"] == expected_sha, "manifest_sha_mismatch")
    require(manifest["runner_instance_id"] == expected_runner_instance_id,
            "manifest_identity_mismatch")
    require(isinstance(manifest["runner_instance_id"], str) and
            bool(INSTANCE.fullmatch(manifest["runner_instance_id"])),
            "manifest_identity_invalid")
    require(manifest["runner_labels"] == policy["required_runner_labels"] and
            manifest["capabilities"] == policy["required_tools"], "manifest_capability_invalid")
    require(manifest["safeguards"] == {
        "hml_enabled": False, "stg_enabled": False,
        "production_enabled": False, "automatic_retry_enabled": False,
    }, "manifest_safeguards_invalid")
    require(isinstance(manifest["runtime_root"], str) and
            root.is_absolute() and root.is_dir() and
            str(root) == manifest["runtime_root"], "runtime_root_invalid")
    require(_no_reparse(root), "runtime_reparse_refused")
    require(not {x.casefold() for x in root.parts}.intersection(
        {"hml", "stg", "prod", "production"}), "non_dev_root_refused")
    require(all(which(tool) for tool in policy["required_tools"]),
            "native_tool_missing")
    return {"status": "LOCAL_PREFLIGHT_ONLY", "ready_for_work": False,
            "dispatch_allowed": False, "gateway_validated": False,
            "independent_receipt_validated": False, "continuity_certified": False,
            "source_sha": expected_sha,
            "runner_instance_id": manifest["runner_instance_id"]}


def verify_gateway_source(policy: dict[str, Any], bundle: dict[str, Any],
                          receipt: dict[str, Any], attestation: dict[str, Any], *,
                          verifier_key: bytes, expected_sha: str,
                          expected_runner_instance_id: str,
                          expected_github_run_id: int,
                          at: datetime | None = None) -> dict[str, Any]:
    """Etapa EXCLUSIVA do Validator externo em ambiente de confiança separado.

    A assinatura cobre o hash exato de três observações: Launcher, Gateway e
    inventário API GitHub. O emissor independente precisa obter/verificar as
    observações antes de assinar. JSON vindo do próprio runner nunca é prova.
    """
    validate_contract(policy)
    require(isinstance(verifier_key, bytes) and len(verifier_key) >= 32,
            "validator_key_missing")
    require(isinstance(expected_sha, str) and bool(SHA40.fullmatch(expected_sha)),
            "expected_sha_invalid")
    require(isinstance(expected_runner_instance_id, str) and
            bool(INSTANCE.fullmatch(expected_runner_instance_id)),
            "expected_runner_invalid")
    require(type(expected_github_run_id) is int and expected_github_run_id > 0,
            "expected_run_invalid")
    require(isinstance(bundle, dict) and set(bundle) == BUNDLE_KEYS and
            bundle["schema_version"] == 1, "gateway_bundle_invalid")
    launcher, gateway, github = (bundle[k] for k in ("launcher", "gateway", "github"))
    require(all(isinstance(v, dict) for v in (launcher, gateway, github)),
            "gateway_bundle_invalid")
    require(set(launcher) == {"result", "state_validated", "head", "session_id",
                                "host", "profile", "worktree_exclusive", "lease_exclusive"},
            "launcher_contract_invalid")
    require(launcher["result"] == "SESSION_LAUNCH_OK" and
            launcher["state_validated"] is True and launcher["head"] == expected_sha
            and launcher["profile"] == "NORMAL" and
            launcher["worktree_exclusive"] is True and
            launcher["lease_exclusive"] is True and
            isinstance(launcher["session_id"], str) and len(launcher["session_id"]) >= 12,
            "session_launcher_unverified")
    require(set(gateway) == {"result", "gateway_exit_code", "state_changed",
                               "head", "session_id", "command_tag", "correlation_id"},
            "gateway_contract_invalid")
    require(gateway["result"] == "ok" and type(gateway["gateway_exit_code"]) is int
            and gateway["gateway_exit_code"] == 0 and gateway["state_changed"] is False
            and gateway["head"] == expected_sha
            and gateway["session_id"] == launcher["session_id"]
            and gateway["command_tag"] == COMMAND_TAG
            and isinstance(gateway["correlation_id"], str)
            and len(gateway["correlation_id"]) >= 12,
            "gateway_readback_unverified")
    require(set(github) == {"source", "run_id", "runner_instance_id", "physical_host_id",
                              "status", "busy", "labels", "head_sha", "observed_at"},
            "github_inventory_contract_invalid")
    require(github["source"] == "github_rest_independent_readback"
            and type(github["run_id"]) is int
            and github["run_id"] == expected_github_run_id
            and github["head_sha"] == expected_sha
            and github["runner_instance_id"] == expected_runner_instance_id
            and github["labels"] == policy["required_runner_labels"]
            and github["status"] == "online" and github["busy"] is False
            and github["physical_host_id"] == launcher["host"],
            "github_inventory_unverified")
    try:
        observed = datetime.fromisoformat(github["observed_at"])
    except (ValueError, TypeError):
        raise NativeAdmissionBlocked("github_observation_invalid") from None
    current = at or datetime.now(timezone.utc)
    require(current.tzinfo is not None and observed.tzinfo is not None and
            0 <= (current - observed).total_seconds() <= policy["max_receipt_age_seconds"],
            "github_inventory_stale")
    require(isinstance(attestation, dict) and set(attestation) == {"payload", "signature"},
            "attestation_envelope_invalid")
    claim = attestation["payload"]
    require(isinstance(claim, dict) and set(claim) == ATTESTATION_KEYS,
            "attestation_fields_invalid")
    require(claim["schema_version"] == 1 and claim["issuer"] == ISSUER
            and claim["source_sha"] == expected_sha
            and claim["runner_instance_id"] == expected_runner_instance_id,
            "attestation_scope_invalid")
    try:
        bundle_hash = hashlib.sha256(_canonical_bytes(bundle)).hexdigest()
        receipt_hash = hashlib.sha256(_canonical_bytes(receipt)).hexdigest()
        claim_bytes = _canonical_bytes(claim)
    except (ValueError, TypeError, OverflowError):
        raise NativeAdmissionBlocked("canonical_payload_invalid") from None
    require(isinstance(claim["bundle_sha256"], str) and
            bool(HEX64.fullmatch(claim["bundle_sha256"])) and
            hmac.compare_digest(claim["bundle_sha256"], bundle_hash),
            "bundle_digest_mismatch")
    require(isinstance(claim["receipt_sha256"], str) and
            bool(HEX64.fullmatch(claim["receipt_sha256"])) and
            hmac.compare_digest(claim["receipt_sha256"], receipt_hash),
            "receipt_digest_mismatch")
    require(isinstance(attestation["signature"], str)
            and bool(HEX64.fullmatch(attestation["signature"]))
            and hmac.compare_digest(attestation["signature"],
                                    hmac.new(verifier_key, claim_bytes, hashlib.sha256).hexdigest()),
            "attestation_signature_invalid")
    try:
        issued = datetime.fromisoformat(claim["issued_at"])
    except (ValueError, TypeError):
        raise NativeAdmissionBlocked("attestation_time_invalid") from None
    require(issued.tzinfo is not None and
            0 <= (current-issued).total_seconds() <= policy["max_receipt_age_seconds"],
            "attestation_time_invalid")
    validated = verify_independent_receipt(
        policy, receipt, verifier_key=verifier_key,
        expected_sha=expected_sha,
        expected_runner_instance_id=expected_runner_instance_id, at=current,
    )
    require(validated["status"] == "signed_receipt_validated" and
            receipt["payload"]["physical_host_id"] == github["physical_host_id"] and
            receipt["payload"]["runner_labels"] == github["labels"],
            "receipt_inventory_mismatch")
    # Assinatura e vínculo são um gate de evidência, nunca autorização de despacho.
    return {"status": "INDEPENDENT_GATEWAY_BINDING_VALIDATED",
            "source_sha": expected_sha, "ready_for_work": False,
            "dispatch_allowed": False, "continuity_certified": False,
            "independent_receipt_validated": True,
            "gateway_provenance_bound": True,
            "github_run_id": expected_github_run_id,
            "physical_host_id": github["physical_host_id"]}


def _json_file(path: Path) -> dict[str, Any]:
    try:
        require(path.is_file() and path.stat().st_size <= 65536, "input_missing_or_oversized")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise NativeAdmissionBlocked("input_unavailable_or_invalid") from None
    require(isinstance(value, dict), "input_not_object")
    return value


def main() -> int:
    p = argparse.ArgumentParser(description="Read-only native DEV proof; no dispatch")
    p.add_argument("--mode", choices=("local", "independent"), required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--runner-instance-id", required=True)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--bundle", type=Path)
    p.add_argument("--receipt", type=Path)
    p.add_argument("--attestation", type=Path)
    p.add_argument("--github-run-id", type=int)
    try:
        args = p.parse_args()
        policy = _json_file(args.policy)
        if args.mode == "local":
            require(args.manifest is not None and args.bundle is None and
                    args.receipt is None and args.attestation is None,
                    "local_inputs_invalid")
            user_dir = os.environ.get("LOCALAPPDATA", "")
            require(bool(user_dir) and args.manifest.is_absolute() and
                    args.manifest.parent == Path(user_dir) / "ReqSys" and
                    _no_reparse(args.manifest), "native_user_manifest_required")
            manifest = _json_file(args.manifest)
            result = local_preflight(
                policy, manifest, expected_sha=args.expected_sha,
                expected_runner_instance_id=args.runner_instance_id, root=Path(manifest.get("runtime_root", "")),
                os_name=os.name, architecture=os.environ.get("PROCESSOR_ARCHITECTURE", ""),
            )
        else:
            require(args.manifest is None and args.bundle is not None and
                    args.receipt is not None and args.attestation is not None and
                    args.github_run_id is not None, "independent_inputs_invalid")
            require(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
                    and os.environ.get("GITHUB_ACTIONS") == "true"
                    and os.environ.get("GITHUB_REPOSITORY") == ALLOWED_REPO,
                    "independent_hosted_context_required")
            key = os.environ.get("REQSYS_NATIVE_VALIDATOR_KEY", "").encode()
            result = verify_gateway_source(
                policy, _json_file(args.bundle), _json_file(args.receipt),
                _json_file(args.attestation), verifier_key=key,
                expected_sha=args.expected_sha,
                expected_runner_instance_id=args.runner_instance_id,
                expected_github_run_id=args.github_run_id,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except NativeAdmissionBlocked as exc:
        print(json.dumps({"status": "BLOCKED_NATIVE_DEV_PREFLIGHT",
                          "reason_code": str(exc), "ready_for_work": False,
                          "dispatch_allowed": False, "continuity_certified": False}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
