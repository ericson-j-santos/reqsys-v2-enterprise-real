"""E2E do perfil real via API DEV; executado no Noteri, sem reconciliar Desktop."""
from __future__ import annotations
import argparse
import json
import os
import re
import socket
import subprocess
from pathlib import Path
from scripts import noteri_study_mode_dev_reconcile as api
from scripts import noteri_supervisor_resume as proc

GATEWAY = "http://DESKTOP-PDQK954:8083"
PROFILE_PATH = "/api/v1/noteri/profile"
CONFIRM = "VALIDATE-NOTERI-PROFILE-DEV"


def validate_data(data, expected):
    if data.get("host") != "Noteri" or data.get("profile") != expected:
        raise proc.Blocked("api_profile_readback_mismatch")
    if data.get("accepts_new_development") is not (expected == "NORMAL"):
        raise proc.Blocked("development_admission_mismatch")


def independent(expected, ps, before):
    profile = Path(os.environ["LOCALAPPDATA"]) / "ReqSys/TodoGlobal24x7/host-profile.json"
    if proc.load(profile).get("profile") != expected:
        raise proc.Blocked("local_profile_readback_mismatch")
    registry = proc.registry()
    if registry["profile"] != expected or not all(registry[k] for k in ("fresh", "auth_valid", "controller_online", "profile_capable")):
        raise proc.Blocked("registry_profile_readback_mismatch")
    current = proc.collect_processes(ps)
    proc.decision(current)
    if current["processes"] != before["processes"]:
        raise proc.Blocked("maintenance_process_identity_changed")
    return {"profile": expected, "local_sha256": proc.sha(proc.read(profile)),
            "last_heartbeat": registry["last_heartbeat"], "processes_unchanged": True}


def run(correlation):
    # Reuse only HTTP helpers; never call execute(), Docker or any host reconciler.
    api.GATEWAY = GATEWAY
    ps = proc.library()
    processes = proc.collect_processes(ps)
    if proc.decision(processes) != "existing" or len(processes["processes"]) != 2:
        raise proc.Blocked("maintenance_not_ready")
    _, auth = api.http_json("GET", "/api/v1/auth/config", stage="auth_config")
    if (auth.get("data") or {}).get("demo_login_enabled") is not True:
        raise proc.Blocked("existing_dev_auth_unavailable")
    api.http_json("GET", PROFILE_PATH, expected={401}, stage="unauthenticated_control")
    token, user = api.login_admin(stage="existing_dev_admin_login")
    _, current = api.http_json("GET", PROFILE_PATH, token=token, stage="initial_profile")
    initial = api.profile_data(current).get("profile")
    if initial not in ("NORMAL", "ESTUDO"):
        raise proc.Blocked("initial_profile_invalid")
    outcomes, mutated, complete = [], False, False
    try:
        for index, profile in enumerate(("NORMAL", "ESTUDO", "ESTUDO", "NORMAL")):
            cid = correlation + "-" + str(index)
            mutated = True  # A network timeout after POST does not prove absence of mutation.
            _, response = api.http_json("POST", PROFILE_PATH, token=token,
                correlation_id=cid, body={"profile": profile, "correlation_id": cid},
                stage="profile_step_" + str(index))
            data = api.profile_data(response)
            validate_data(data, profile)
            if index == 1 and data.get("changed") is not True:
                raise proc.Blocked("estudo_transition_not_observed")
            if index == 2 and data.get("changed") is not False:
                raise proc.Blocked("estudo_replay_not_idempotent")
            _, response = api.http_json("GET", PROFILE_PATH, token=token, stage="api_readback_" + str(index))
            validate_data(api.profile_data(response), profile)
            proof = independent(profile, ps, processes)
            outcomes.append({**proof, "changed": data.get("changed")})
        complete = True
        return {"ok": True, "initial_profile": initial, "final_profile": "NORMAL",
                "negative_auth_status": 401, "steps": outcomes, "browser_ui_tested": False}
    finally:
        if mutated and not complete:
            cid = correlation + "-restore"
            api.http_json("POST", PROFILE_PATH, token=token, correlation_id=cid,
                body={"profile": initial, "correlation_id": cid}, stage="restore_initial_profile")
            independent(initial, ps, processes)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expected-sha", required=True)
    p.add_argument("--correlation-id", required=True)
    p.add_argument("--confirm", required=True)
    a = p.parse_args()
    try:
        if os.name != "nt" or socket.gethostname().casefold() != "noteri" or a.confirm != CONFIRM:
            raise proc.Blocked("host_or_confirmation_invalid")
        if not re.fullmatch("[0-9a-f]{40}", a.expected_sha) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,90}", a.correlation_id):
            raise proc.Blocked("source_or_correlation_invalid")
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parents[1],
                              capture_output=True, text=True, timeout=10)
        if head.returncode or head.stdout.strip() != a.expected_sha:
            raise proc.Blocked("source_sha_mismatch")
        with proc.exclusive():
            result = run(a.correlation_id)
        result.update({"source_sha": a.expected_sha, "correlation_id": a.correlation_id,
                       "host": "Noteri", "environment": "dev", "desktop_services_changed": False})
        print(json.dumps(result, sort_keys=True))
        return 0
    except api.ReconcileError as exc:
        print(json.dumps({"ok": False, "reason": exc.code, "stage": exc.stage,
                          "diagnostic_code": exc.diagnostic_code, "source_sha": a.expected_sha}))
        return 2
    except (proc.Blocked, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"ok": False, "reason": str(exc) if isinstance(exc, proc.Blocked)
                          else type(exc).__name__, "source_sha": a.expected_sha}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
