#!/usr/bin/env python3
"""Read-only adapter for the EXISTING Worker Pool API.

Does not attest physical host identity, issue Ed25519 witnesses, create leases,
change task state, or authorize dispatch. Production credentials stay outside PCs.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import ssl
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, build_opener
from scripts.reqsys_native_external_sources import origin_checked
from scripts.validate_reqsys_native_dev_profile import NativeAdmissionBlocked, _canonical_bytes

REPO = "ericson-j-santos/reqsys-v2-enterprise-real"
TASK = re.compile(r"cwp-[a-f0-9]{24}\Z")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
ROUTES = re.compile(r"/v1/tasks/cwp-[a-f0-9]{24}(?:/diagnostics|/checkpoints/latest)?\Z")
MAX_BYTES = 65536

def _need(condition: bool, code: str) -> None:
    if not condition:
        raise NativeAdmissionBlocked(code)

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int,
                         msg: str, headers: Any, newurl: str) -> None:
        return None

def _protected_token_file(path: Path) -> str:
    _need(isinstance(path, Path) and path.is_absolute() and not path.is_symlink(),
          "workerpool_token_unavailable")
    # Windows ACL validation is not implemented. The trusted observer must be POSIX.
    _need(os.name == "posix", "workerpool_external_posix_required")
    try:
        for parent in (path.parent, *path.parents):
            _need(not parent.is_symlink(), "workerpool_token_path_redirected")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(fd)
            _need(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                  and info.st_mode & 0o077 == 0 and 0 < info.st_size <= 4096,
                  "workerpool_token_permissions")
            token = os.read(fd, 4097).decode("ascii").strip()
        finally:
            os.close(fd)
    except NativeAdmissionBlocked:
        raise
    except (OSError, UnicodeError):
        raise NativeAdmissionBlocked("workerpool_token_unavailable") from None
    _need(24 <= len(token) <= 4096 and re.fullmatch(r"[!-~]+", token) is not None,
          "workerpool_token_invalid")
    return token

class WorkerPoolGET:
    """Fixed authenticated GET transport; no arbitrary paths or redirects."""
    def __init__(self, *, origin: str, token_file: Path, ca_file: Path | None = None):
        self.origin = origin_checked(origin)
        self._token = _protected_token_file(token_file)
        if ca_file is not None:
            _need(isinstance(ca_file, Path) and ca_file.is_absolute() and
                  ca_file.is_file() and not ca_file.is_symlink(),
                  "workerpool_ca_unavailable")
        try:
            context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
        except (OSError, ssl.SSLError, ValueError):
            raise NativeAdmissionBlocked("workerpool_ca_unavailable") from None
        _need(context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname,
              "workerpool_tls_not_verified")
        self._opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), _NoRedirect())

    def get(self, path: str) -> dict[str, Any]:
        _need(isinstance(path, str) and ROUTES.fullmatch(path) is not None,
              "workerpool_route_forbidden")
        request = Request(self.origin + path, method="GET", headers={
            "Authorization": "Bearer " + self._token, "Accept": "application/json",
            "User-Agent": "reqsys-independent-workerpool-readback/1",
        })
        try:
            with self._opener.open(request, timeout=5) as response:
                _need(response.status == 200, "workerpool_response_invalid")
                _need(response.headers.get_content_type() == "application/json",
                      "workerpool_content_type_invalid")
                body = response.read(MAX_BYTES + 1)
        except (OSError, HTTPError, URLError, TimeoutError):
            raise NativeAdmissionBlocked("workerpool_get_unavailable") from None
        _need(len(body) <= MAX_BYTES, "workerpool_response_oversized")
        try:
            result = json.loads(body.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise NativeAdmissionBlocked("workerpool_json_invalid") from None
        _need(type(result) is dict, "workerpool_json_invalid")
        return result

def read_workerpool_checkpoint(*, get: Callable[[str], dict[str, Any]],
                               task_id: str, expected_source_sha: str,
                               expected_worker_id: str, expected_generation: int,
                               expected_artifact_sha256: str,
                               at: datetime | None = None) -> dict[str, Any]:
    """Cross-check 4 authenticated GETs; never treat as an exclusive-lease witness."""
    _need(type(task_id) is str and TASK.fullmatch(task_id) is not None,
          "workerpool_task_invalid")
    _need(type(expected_source_sha) is str and SHA40.fullmatch(expected_source_sha) is not None,
          "workerpool_sha_invalid")
    _need(type(expected_artifact_sha256) is str
          and SHA64.fullmatch(expected_artifact_sha256) is not None,
          "workerpool_digest_invalid")
    _need(type(expected_worker_id) is str and
          re.fullmatch(r"[a-zA-Z0-9_.:-]{8,128}", expected_worker_id) is not None,
          "workerpool_worker_invalid")
    _need(type(expected_generation) is int and expected_generation >= 1,
          "workerpool_generation_invalid")
    _need(callable(get), "workerpool_reader_unavailable")
    base = "/v1/tasks/" + task_id
    try:
        first = get(base)
        diagnosis = get(base + "/diagnostics")
        checkpoint_envelope = get(base + "/checkpoints/latest")
        second = get(base)
    except NativeAdmissionBlocked:
        raise
    except Exception:
        raise NativeAdmissionBlocked("workerpool_readback_unavailable") from None
    _need(all(type(x) is dict for x in (first, diagnosis, checkpoint_envelope, second)),
          "workerpool_payload_invalid")
    stable = ("task_id", "repository", "base_sha", "state", "leased_by",
              "lease_expires_at", "lease_generation", "attempt_id", "fencing_required")
    _need(all(first.get(k) == second.get(k) for k in stable),
          "workerpool_concurrent_change")
    _need(first.get("task_id") == task_id and first.get("repository") == REPO
          and first.get("base_sha") == expected_source_sha
          and first.get("leased_by") == expected_worker_id
          and first.get("lease_generation") == expected_generation
          and first.get("fencing_required") is True
          and first.get("state") in ("leased", "running"),
          "workerpool_task_identity_mismatch")
    raw_expiry = first.get("lease_expires_at")
    try:
        expiry = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        raise NativeAdmissionBlocked("workerpool_lease_expiry_invalid") from None
    now = at or datetime.now(timezone.utc)
    _need(now.tzinfo is not None and expiry.tzinfo is not None and expiry > now,
          "workerpool_lease_expired")
    d = diagnosis.get("task")
    _need(diagnosis.get("read_mode") == "postgres_read_only"
          and diagnosis.get("claim_performed") is False
          and diagnosis.get("reconciliation_requested") is False
          and type(d) is dict and d.get("task_id") == task_id
          and d.get("repository") == REPO and d.get("base_sha") == expected_source_sha
          and d.get("state") == first.get("state")
          and d.get("leased_by") == expected_worker_id
          and d.get("lease_expires_at") == raw_expiry
          and d.get("lease_expired_observed") is False,
          "workerpool_diagnostics_not_independent")
    _need(set(checkpoint_envelope) == {"checkpoint"},
          "workerpool_checkpoint_envelope_invalid")
    cp = checkpoint_envelope["checkpoint"]
    _need(type(cp) is dict and cp.get("task_id") == task_id
          and cp.get("lease_generation") == expected_generation
          and cp.get("artifact_sha256") == expected_artifact_sha256
          and cp.get("effect_state") not in ("pending", "unknown")
          and type(cp.get("checkpoint_id")) is str,
          "workerpool_checkpoint_mismatch")
    # Hash is an observation digest, not the expected durable CAS digest.
    digest = hashlib.sha256(_canonical_bytes(cp)).hexdigest()
    return {
        "status": "WORKER_POOL_READBACK_ONLY",
        "source": "existing_worker_pool_api",
        "task_id": task_id, "source_sha": expected_source_sha,
        "worker_id": expected_worker_id, "lease_generation": expected_generation,
        "artifact_sha256_observed": expected_artifact_sha256,
        "checkpoint_response_sha256": digest,
        "lease_exclusive_certified": False,
        "physical_host_authenticated": False,
        "ready_for_work": False,
        "dispatch_allowed": False,
        "continuity_certified": False,
    }
