import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/codex-ollama-e2e-dev.yml"
SCRIPT = ROOT / "scripts/validate_codex_cloud_reqsys_e2e.py"
GATEWAY = ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml"
POLICY = ROOT / ".github/self-hosted-runner-policy.json"
SPEC = ROOT / ".sdd/specs/codex-cloud-primary-local-fallback.spec.json"


def test_workflow_is_fixed_to_pc24x7_dev_and_sha_bound() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in raw
    assert "schedule:" not in raw
    assert "pull_request:" not in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "actions/setup-python@" not in raw
    assert "Get-Command python -CommandType Application -ErrorAction Stop" in raw
    assert '& "$env:REQSYS_PYTHON" -m pip install' in raw
    assert '& "$env:REQSYS_PYTHON" scripts/validate_codex_cloud_reqsys_e2e.py' in raw
    assert 'DESKTOP-PDQK954' in raw
    assert '--expected-sha "${{ github.sha }}"' in raw
    assert '--correlation-id "$env:CORRELATION_ID"' in raw
    assert '--evidence-file "$env:EVIDENCE_FILE"' in raw
    assert 'gemma4:31b-cloud' in raw
    assert 'gemma4:26b-q8-code' in raw
    assert "Produção tocada: não" in raw
    assert "Deploy executado: não" in raw


def test_script_rejects_sha_drift_and_writes_evidence() -> None:
    raw = SCRIPT.read_text(encoding="utf-8")

    assert 'parser.add_argument("--expected-sha", required=True)' in raw
    assert 'parser.add_argument("--correlation-id", required=True)' in raw
    assert 'parser.add_argument("--evidence-file", type=Path, required=True)' in raw
    assert '["git", "rev-parse", "HEAD"]' in raw
    assert "checkout SHA divergente" in raw
    assert "_write_evidence(evidence_file, result)" in raw
    assert "_write_evidence(evidence_file, blocked)" in raw
    assert '"correlation_id": f"{correlation_id}-fallback"' in raw
    assert '"X-Correlation-Id": correlation_id' in raw
    assert "E2E publicou indevidamente no ReqSys" in raw
    assert "codex-cloud-e2e-20260919" not in raw


def test_authorized_gateway_has_exact_ollama_e2e_route_and_cleanup() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")

    assert "github.event.issue.number == 1705" in raw
    assert "github.event.comment.user.login == 'ericson-j-santos'" in raw
    assert "github.event.comment.body == '/reqsys run codex-ollama-e2e-dev'" in raw
    assert "target='codex-ollama-e2e-dev.yml'" in raw
    assert "steps.route.outputs.target == 'codex-ollama-e2e-dev.yml'" in raw
    assert "SELF_HOSTED_RUNNER_PICKUP_TIMEOUT_OR_BUSY" in raw
    assert 'gh run cancel "$TARGET_RUN_ID"' in raw


def test_self_hosted_policy_and_sdd_explicitly_allowlist_ollama_e2e() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))

    assert ".github/workflows/codex-ollama-e2e-dev.yml" in policy["approved_workflows"]
    assert policy["required_adr"] == "docs/adr/ADR-046-pc24x7-substituicao-flyio.md"
    assert ".github/workflows/codex-ollama-e2e-dev.yml" in spec["runtime_validation"]["workflow"]
    assert "tests/test_codex_ollama_e2e_selfhosted.py" in spec["sdd_gate"]["tests"]


def test_change_impact_pr2144_mode_is_pr_bound_and_fail_closed() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "- change-impact-pr2144" in raw
    assert "target_sha:" in raw
    assert "actions/checkout@v4" not in raw
    assert raw.count("actions/checkout@11d5960a326750d5838078e36cf38b85af677262") == 3
    assert "pull-requests: read" in raw
    assert "pulls/2144" in raw
    assert 'copilot/change-impact-benchmark-20260928' in raw
    assert "PR2144_NOT_CLOSED" in raw\n    assert "PR2144_NOT_MERGED" in raw
    assert "PR2144_BASE_NOT_MAIN" in raw
    assert "PR2144_HEAD_REPOSITORY_MISMATCH" in raw
    assert "PR2144_HEAD_BRANCH_MISMATCH" in raw
    assert "PR2144_MERGE_SHA_MISMATCH" in raw
    assert 'ref: ${{ inputs.target_sha }}' in raw
    assert "TARGET_SHA_CHECKOUT_MISMATCH" in raw
    assert "scripts/change_impact_benchmark.py" in raw
    assert "--llm-mode configured" in raw
    assert "--provider ollama_gateway" in raw
    assert "--require-llm" in raw
    assert "BENCHMARK_LLM_NOT_USED_FOR_ALL_CASES" in raw
    assert "BENCHMARK_HYBRID_NOT_USED" in raw
    assert "benchmark_sha256" in raw
    assert "production_touched = $false" in raw
    assert "deploy_performed = $false" in raw


def test_authorized_gateway_binds_change_impact_command_to_pr2144_merge_commit() -> None:
    raw = GATEWAY.read_text(encoding="utf-8")

    assert "github.event.comment.body == '/reqsys run change-impact-benchmark-pr2144'" in raw
    assert "'/reqsys run change-impact-benchmark-pr2144')" in raw
    assert "mode='change-impact-pr2144'" in raw
    assert 'gh api "repos/${GITHUB_REPOSITORY}/pulls/2144"' in raw
    assert "change_impact_pr2144_not_closed" in raw\n    assert "change_impact_pr2144_not_merged" in raw
    assert "change_impact_pr2144_base_mismatch" in raw
    assert "change_impact_pr2144_repo_mismatch" in raw
    assert "change_impact_pr2144_branch_mismatch" in raw
    assert "change_impact_pr2144_merge_sha_invalid" in raw
    assert '-f target_sha="$CHANGE_IMPACT_TARGET_SHA"' in raw
    assert "'workload_sha': os.environ.get('CHANGE_IMPACT_TARGET_SHA') or None" in raw
