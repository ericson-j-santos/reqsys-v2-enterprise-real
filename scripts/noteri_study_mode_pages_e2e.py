#!/usr/bin/env python3
"""E2E DEV do Task Console com sessão Microsoft real, sem login demonstrativo.

Requer runner Desktop, sessão governada e um bundle MSAL autorizado no segredo
REQSYS_NOTERI_DEV_MSAL_STATE_B64. Nunca emite credenciais nem altera containers.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

import noteri_study_mode_dev_reconcile as legacy
import verify_self_hosted_dev_azure_auth as msal_proof

HOST = "DESKTOP-PDQK954"
PAGES = "https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev"
PAGES_ORIGIN = "https://ericson-j-santos.github.io"
MSAL_ENV = "REQSYS_NOTERI_DEV_MSAL_STATE_B64"
CONFIRM = "RECONCILE-NOTERI-STUDY-MODE-DEV"


class E2EBlocked(Exception):
    pass


def require_exact_environment(repo: Path, sha: str, confirm: str) -> None:
    if confirm != CONFIRM or os.name != "nt" or socket.gethostname().upper() != HOST:
        raise E2EBlocked("dev_host_or_confirmation_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise E2EBlocked("expected_sha_invalid")
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True,
        text=True, shell=False, check=False, timeout=20,
    )
    if proc.returncode or proc.stderr.strip() or proc.stdout.strip().lower() != sha:
        raise E2EBlocked("worktree_sha_mismatch")
    _, body = legacy.http_json("GET", "/api/runtime/build-info", stage="runtime_sha")
    data = body.get("data", body)
    if data.get("build_sha") != sha:
        raise E2EBlocked("runtime_sha_mismatch")
    for route in ("/api/health", "/api/runtime/health", "/api/runtime/readiness"):
        legacy.http_json("GET", route, stage="runtime_health")


def load_authorized_msal_state(config: dict, encoded: str) -> list[dict]:
    if not encoded or len(encoded) > 2800000:
        raise E2EBlocked("msal_state_missing_or_oversized")
    if (
        config.get("environment") != "desenvolvimento"
        or config.get("azure_enabled") is not True
        or config.get("demo_login_enabled") is not False
        or config.get("expected_redirect_uri") != PAGES + "/auth/callback.html"
    ):
        raise E2EBlocked("azure_dev_contract_invalid")
    try:
        raw = base64.b64decode(encoded, validate=True)
        bundle = json.loads(raw)
    except (ValueError, UnicodeError, binascii.Error, TypeError) as exc:
        raise E2EBlocked("msal_state_invalid") from exc
    if (
        not isinstance(bundle, dict)
        or bundle.get("schemaVersion") != 1
        or bundle.get("origin") != PAGES_ORIGIN
        or not isinstance(bundle.get("sessionStorage"), list)
    ):
        raise E2EBlocked("msal_state_wrong_origin_or_schema")
    try:
        # Verifica tenant/audience/issuer e expiracao antes de abrir o navegador.
        msal_proof.supplied_id_token(encoded, config, int(time.time()) + 180)
    except msal_proof.ProofError as exc:
        raise E2EBlocked("msal_state_claims_invalid_or_expired") from exc
    entries = bundle["sessionStorage"]
    if len(entries) > 120 or any(
        not isinstance(e, dict)
        or not isinstance(e.get("name"), str)
        or not isinstance(e.get("value"), str)
        or len(e["name"]) > 200
        or len(e["value"]) > 100000
        for e in entries
    ):
        raise E2EBlocked("msal_cache_invalid")
    # Nao importamos cookies, JWT do ReqSys ou dados de outro dominio.
    selected = [
        {"name": e["name"], "value": e["value"]}
        for e in entries if e["name"].lower().startswith("msal.")
    ]
    if not selected:
        raise E2EBlocked("msal_cache_absent")
    return selected


def profile(token: str, expected: str) -> None:
    _, payload = legacy.http_json(
        "GET", "/api/v1/noteri/profile", token=token,
        stage="profile_readback",
    )
    data = legacy.profile_data(payload)
    if (
        data.get("profile") != expected
        or data.get("accepts_new_development") is not (expected == "NORMAL")
    ):
        raise E2EBlocked("profile_readback_inconsistent")


def worker(expected: str) -> None:
    deadline = time.monotonic() + 18
    while True:
        report = legacy.probe_control_plane_worker_registry()
        state = report.get("noteri") or {}
        if (
            report.get("payload_valid") is True
            and report.get("noteri_match_count") == 1
            and state.get("fresh") is True
            and state.get("controller_online") is True
            and state.get("auth_valid") is True
            and state.get("profile") == expected
        ):
            return
        if time.monotonic() >= deadline:
            raise E2EBlocked("worker_readback_unavailable")
        time.sleep(1)


def post_profile(token: str, target: str, correlation: str) -> dict:
    _, data = legacy.http_json(
        "POST", "/api/v1/noteri/profile", token=token,
        correlation_id=correlation,
        body={"profile": target, "correlation_id": correlation},
        stage="profile_post",
    )
    return legacy.profile_data(data)


def restore_normal(token: str, correlation: str) -> None:
    try:
        post_profile(token, "NORMAL", correlation + "-restore")
        profile(token, "NORMAL")
        worker("NORMAL")
    except Exception as exc:
        raise E2EBlocked("normal_restore_not_confirmed") from exc


def check_before_mutation(token: str, correlation: str) -> None:
    unauthorized, _ = legacy.http_json(
        "GET", "/api/v1/noteri/profile", expected={401},
        stage="unauthenticated_negative",
    )
    if unauthorized != 401:
        raise E2EBlocked("unauthenticated_not_rejected")
    session_payload = legacy.http_json(
        "GET", "/api/v1/auth/session", token=token,
        stage="msal_backend_session",
    )[1]
    if (session_payload.get("data") or {}).get("papel") != "admin":
        raise E2EBlocked("test_identity_not_admin")
    profile(token, "NORMAL")
    worker("NORMAL")
    mismatch, _ = legacy.http_json(
        "POST", "/api/v1/noteri/profile", token=token,
        correlation_id=correlation + "-header",
        body={"profile": "ESTUDO", "correlation_id": correlation + "-body"},
        expected={409}, stage="correlation_negative",
    )
    if mismatch != 409:
        raise E2EBlocked("correlation_mismatch_not_rejected")
    profile(token, "NORMAL")
    worker("NORMAL")


def require_chip(page, target: str) -> None:
    page.wait_for_function(
        """target => {
          const card = document.querySelector('[data-testid="noteri-study-mode-card"]');
          const chip = card && card.querySelector('.v-chip');
          return chip && chip.textContent.trim() === target;
        }""",
        arg=target,
        timeout=30000,
    )


def browser_e2e(entries: list[dict], correlation: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise E2EBlocked("playwright_unavailable") from exc
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        attempted = False
        verified = False
        token = ""
        try:
            context = browser.new_context(ignore_https_errors=False)
            context.add_init_script(
                """items => {
                  if (location.origin !== 'https://ericson-j-santos.github.io') return;
                  items.forEach(item => sessionStorage.setItem(item.name, item.value));
                }""",
                arg=entries,
            )
            page = context.new_page()
            page.goto(PAGES + "/task-console", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_function(
                "() => Boolean(localStorage.getItem('reqsys_token'))",
                timeout=30000,
            )
            token = page.evaluate("localStorage.getItem('reqsys_token')")
            check_before_mutation(token, correlation)
            require_chip(page, "NORMAL")
            start = page.get_by_role("button", name="Quero estudar agora")
            if start.is_disabled():
                raise E2EBlocked("study_button_disabled")
            attempted = True
            start.click()
            require_chip(page, "ESTUDO")
            profile(token, "ESTUDO")
            worker("ESTUDO")
            replay = post_profile(token, "ESTUDO", correlation + "-replay")
            if replay.get("changed") is not False:
                raise E2EBlocked("replay_changed_unexpectedly")
            page.get_by_role("button", name="Voltar ao desenvolvimento").click()
            require_chip(page, "NORMAL")
            profile(token, "NORMAL")
            worker("NORMAL")
            verified = True
            return {
                "msal_backend_session_verified": True,
                "negative_401_and_409": True,
                "ui_and_worker_estudo": True,
                "replay_idempotent": True,
                "normal_restored": True,
                "final_profile": "NORMAL",
            }
        finally:
            try:
                if attempted and not verified and token:
                    restore_normal(token, correlation)
            finally:
                browser.close()


def run(repo: Path, sha: str, confirmation: str, correlation: str) -> dict:
    require_exact_environment(repo, sha, confirmation)
    _, auth = legacy.http_json("GET", "/api/v1/auth/config", stage="auth_config")
    entries = load_authorized_msal_state(
        auth.get("data") or {}, os.environ.get(MSAL_ENV, ""),
    )
    result = browser_e2e(entries, correlation)
    return {
        "ok": True, "environment": "dev", "host": HOST,
        "source_sha": sha, "runtime_sha": sha, "correlation_id": correlation,
        "browser_e2e": result,
        "production_touched": False, "credentials_exposed": False,
    }


def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument("--repo-root", type=Path, required=True)
    args.add_argument("--expected-sha", required=True)
    args.add_argument("--confirm", required=True)
    args.add_argument("--correlation-id", required=True)
    args.add_argument("--evidence-path", type=Path, required=True)
    params = args.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{8,110}", params.correlation_id):
            raise E2EBlocked("correlation_id_invalid")
        result = run(params.repo_root, params.expected_sha, params.confirm, params.correlation_id)
    except Exception as exc:
        result = {
            "ok": False, "environment": "dev", "host": HOST,
            "source_sha": params.expected_sha, "correlation_id": params.correlation_id,
            "error_code": str(exc) if isinstance(exc, E2EBlocked) else "e2e_unexpected_error",
            "production_touched": False, "credentials_exposed": False,
        }
    params.evidence_path.parent.mkdir(parents=True, exist_ok=True)
    params.evidence_path.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
