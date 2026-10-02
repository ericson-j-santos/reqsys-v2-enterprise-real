"""Impede que operacoes Fly.io voltem a executar nos workflows."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FLY = re.compile(r"flyctl|superfly/|FLY_API_TOKEN|FLY_APP|fly-environment-(?:promotion-stage|evidence-capture)\.yml", re.I)
FLY_URL = re.compile(
    r"(?:https?://(?:[a-z0-9*_-]+\.)*fly\.(?:dev|io)\b|(?:[a-z0-9_-]+\.)+fly\.(?:dev|io)\b|\*fly\.(?:dev|io)\*)",
    re.I,
)
INNOCUOUS_FLY_URL_GUARDS = (
    "*fly.io*|*fly.dev*",
    "https://*.fly.dev|https://*.fly.dev/*",
)

def permanently_blocked(job):
    condition = str(job.get("if", "")).strip()
    return condition == "${{ false }}" or bool(re.fullmatch(r"\$\{\{\s*false\s*&&\s*\([\s\S]*\)\s*\}\}", condition))

def active_fly_jobs(workflow):
    return [name for name, job in workflow.get("jobs", {}).items()
            if FLY.search(json.dumps(job)) and not permanently_blocked(job)]

def active_fly_url_jobs(workflow):
    violations = []
    for name, job in workflow.get("jobs", {}).items():
        serialized = json.dumps(job)
        for guard in INNOCUOUS_FLY_URL_GUARDS:
            serialized = serialized.replace(guard, "")
        if FLY_URL.search(serialized) and not permanently_blocked(job):
            violations.append(name)
    return violations

def test_flyio_jobs_are_permanently_blocked():
    violations = {}
    for path in (ROOT / ".github/workflows").iterdir():
        if path.suffix in (".yml", ".yaml"):
            jobs = active_fly_jobs(yaml.safe_load(path.read_text(encoding="utf-8")))
            if jobs:
                violations[path.name] = jobs
    assert not violations, violations

def test_flyio_url_jobs_are_permanently_blocked():
    violations = {}
    for path in (ROOT / ".github/workflows").iterdir():
        if path.suffix in (".yml", ".yaml"):
            jobs = active_fly_url_jobs(yaml.safe_load(path.read_text(encoding="utf-8")))
            if jobs:
                violations[path.name] = jobs
    assert not violations, violations

def test_guard_detects_reactivation_and_allows_other_providers():
    assert active_fly_jobs({"jobs": {"deploy": {"steps": [{"run": "flyctl deploy"}]}}}) == ["deploy"]
    assert not active_fly_jobs({"jobs": {"deploy": {"if": "${{ false }}", "steps": [{"run": "flyctl deploy"}]}}})
    assert not active_fly_jobs({"jobs": {"build": {"steps": [{"run": "npm run build"}]}}})

    assert not permanently_blocked({"if": "${{ false || true }}"})
    assert permanently_blocked({"if": "${{ false && (always()) }}"})

def test_url_guard_detects_calls_but_allows_rejection_only_guards():
    active_call = {"jobs": {"smoke": {"steps": [{"run": "curl https://reqsys-api-dev.fly.dev/health"}]}}}
    blocked_call = {"jobs": {"smoke": {"if": "${{ false }}", "steps": active_call["jobs"]["smoke"]["steps"]}}}
    rejection_guard = {"jobs": {"guard": {"steps": [{"run": "case \"$url\" in *fly.io*|*fly.dev*) exit 1 ;; esac"}]}}}
    guard_and_call = {"jobs": {"smoke": {"steps": [{"run": "case \"$url\" in *fly.io*|*fly.dev*) exit 1 ;; esac\ncurl https://reqsys-api-dev.fly.dev/health"}]}}}

    assert active_fly_url_jobs(active_call) == ["smoke"]
    assert not active_fly_url_jobs(blocked_call)
    assert not active_fly_url_jobs(rejection_guard)
    assert active_fly_url_jobs(guard_and_call) == ["smoke"]
    assert active_fly_url_jobs({"jobs": {"smoke": {"env": {"URL": "reqsys-api-dev.fly.dev"}}}}) == ["smoke"]
    assert not active_fly_url_jobs({"jobs": {"smoke": {"steps": [{"run": "curl https://example.com/health"}]}}})
