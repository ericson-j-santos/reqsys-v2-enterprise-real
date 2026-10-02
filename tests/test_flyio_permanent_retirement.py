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


def active_indirect_fly_url_jobs(workflow):
    """Detecta jobs que herdam URL Fly de env/input definido no workflow."""
    violations = set()
    jobs = workflow.get("jobs", {}) or {}

    def references(job, name):
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(str(name))}(?![A-Za-z0-9_])",
                json.dumps(job),
                re.I,
            )
        )

    for name, value in (workflow.get("env", {}) or {}).items():
        if not FLY_URL.search(str(value)):
            continue
        violations.update(
            job_name
            for job_name, job in jobs.items()
            if references(job, name) and not permanently_blocked(job)
        )

    triggers = workflow.get("on", workflow.get(True, {})) or {}
    dispatch = triggers.get("workflow_dispatch", {}) if isinstance(triggers, dict) else {}
    inputs = (dispatch or {}).get("inputs", {}) if isinstance(dispatch, dict) else {}
    for name, spec in (inputs or {}).items():
        default = spec.get("default", "") if isinstance(spec, dict) else ""
        if not FLY_URL.search(str(default)):
            continue
        violations.update(
            job_name
            for job_name, job in jobs.items()
            if references(job, name) and not permanently_blocked(job)
        )

    return sorted(violations)

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


def test_indirect_flyio_url_jobs_are_permanently_blocked():
    violations = {}
    for path in (ROOT / ".github/workflows").iterdir():
        if path.suffix in (".yml", ".yaml"):
            jobs = active_indirect_fly_url_jobs(yaml.safe_load(path.read_text(encoding="utf-8")))
            if jobs:
                violations[path.name] = jobs
    assert not violations, violations


def test_provider_neutral_runtime_defaults_do_not_reference_flyio():
    compose = (ROOT / "docker-compose.pc24x7-teams.yml").read_text(encoding="utf-8")
    observability_readme = (
        ROOT / "services/environment-observability-api/README.md"
    ).read_text(encoding="utf-8")

    assert not FLY_URL.search(compose)
    assert "REQSYS_API_BASE_URL:?" in compose
    assert "fly deploy" not in observability_readme.lower()
    assert "fly apps create" not in observability_readme.lower()


def test_fly_environment_manifest_consumer_is_permanently_blocked():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/fly-enterprise-sync.yml").read_text(encoding="utf-8")
    )
    assert permanently_blocked(workflow["jobs"]["runtime-smoke-readonly"])

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


def test_indirect_url_guard_detects_workflow_env_and_dispatch_defaults():
    inherited_env = {
        "env": {"PUBLIC_URL": "https://reqsys-app.fly.dev"},
        "jobs": {"smoke": {"steps": [{"run": "curl $PUBLIC_URL/health"}]}},
    }
    inherited_input = {
        "on": {
            "workflow_dispatch": {
                "inputs": {"base_url": {"default": "https://reqsys-app.fly.dev"}}
            }
        },
        "jobs": {
            "smoke": {
                "env": {"BASE_URL": "${{ github.event.inputs.base_url }}"},
                "steps": [{"run": "curl $BASE_URL/health"}],
            }
        },
    }

    assert active_indirect_fly_url_jobs(inherited_env) == ["smoke"]
    assert active_indirect_fly_url_jobs(inherited_input) == ["smoke"]
    inherited_env["jobs"]["smoke"]["if"] = "${{ false }}"
    inherited_input["jobs"]["smoke"]["if"] = "${{ false }}"
    assert not active_indirect_fly_url_jobs(inherited_env)
    assert not active_indirect_fly_url_jobs(inherited_input)
