import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/branch-protection-audit.yml"
GATEWAY = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
CONFIG = ROOT / "scripts/configure_reqsys_main_ruleset_risk3.py"
RUNNER_PATH = ROOT / "scripts/run_reqsys_main_ruleset_local.py"

spec = importlib.util.spec_from_file_location("reqsys_ruleset_runner", RUNNER_PATH)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def _ruleset():
    return {
        "id": 17998541,
        "name": "Ruleset",
        "target": "branch",
        "source": "ericson-j-santos/reqsys-v2-enterprise-real",
        "enforcement": "active",
        "bypass_actors": [],
        "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "dismiss_stale_reviews_on_push": False,
                    "required_reviewers": [],
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": False,
                    "require_extra_approval_for_unattributed_changes": True,
                    "allowed_merge_methods": ["merge", "squash", "rebase"],
                },
            },
        ],
    }


def test_reqsys_ruleset_payload_preserva_regras_e_adiciona_checks_canonicos():
    before = _ruleset()
    payload = runner.build_update_payload(before)
    assert payload["conditions"] == before["conditions"]
    assert payload["bypass_actors"] == []
    pull_before = next(rule for rule in before["rules"] if rule["type"] == "pull_request")
    pull_after = next(rule for rule in payload["rules"] if rule["type"] == "pull_request")
    assert pull_after == pull_before
    status = next(rule for rule in payload["rules"] if rule["type"] == "required_status_checks")
    contexts = tuple(item["context"] for item in status["parameters"]["required_status_checks"])
    assert contexts == runner.REQUIRED_CHECKS
    assert status["parameters"]["strict_required_status_checks_policy"] is True
    assert status["parameters"]["do_not_enforce_on_create"] is False


def test_reqsys_ruleset_readback_compliant_so_com_os_oito_checks():
    current = _ruleset()
    update = runner.build_update_payload(current)
    merged = dict(current)
    merged["rules"] = update["rules"]
    assert runner.ruleset_compliant(merged)
    merged["rules"][-1]["parameters"]["required_status_checks"] = [{"context": "Required Fast Gate"}]
    assert not runner.ruleset_compliant(merged)


def test_reqsys_ruleset_automation_e_exata_governada_e_sem_segredo():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    gateway = GATEWAY.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    raw = RUNNER_PATH.read_text(encoding="utf-8")
    assert "apply-reqsys-main" in workflow
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in workflow
    assert "/reqsys run protect-reqsys-main-ruleset" in gateway
    assert "mode='apply-reqsys-main'" in gateway
    assert "apply-reqsys-main-noteri" in workflow
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in workflow
    assert "Checkout ReqSys no SHA governado" in workflow
    assert "TARGET_REPO: ${{ github.workspace }}" in workflow
    assert "/reqsys run protect-reqsys-main-ruleset-noteri" in gateway
    assert "mode='apply-reqsys-main-noteri'" in gateway
    assert "ready_for_review, closed" in workflow
    assert "github.event.pull_request.number == 2079" in workflow
    assert "github.event.pull_request.merged == true" in workflow
    assert "fix/reqsys-main-ruleset-noteri-fallback-20260924" in workflow
    assert "github.event.pull_request.merge_commit_sha" in workflow
    assert 'TARGET_RULESET_ID = 17998541' in raw
    assert 'TARGET_REPOSITORY = "ericson-j-santos/reqsys-v2-enterprise-real"' in raw
    assert 'env.pop("GH_TOKEN", None)' in raw
    assert 'env.pop("GITHUB_TOKEN", None)' in raw
    assert '"required_status_checks"' in raw
    assert '"ruleset_readback_mismatch"' in raw
    assert '"secret_value_exposed": False' in raw
    assert 'ACTION_ID = "reqsys.reqsys-main-ruleset-protection.dev"' in config
    assert 'SCOPE = "repo://ericson-j-santos/reqsys-v2-enterprise-real/ruleset/17998541"' in config
    assert "--token" not in config and "--secret" not in config
