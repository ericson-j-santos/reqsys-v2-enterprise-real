from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATEWAY = (ROOT / ".github/workflows/reqsys-authorized-actions-gateway.yml").read_text(encoding="utf-8")


def test_kubernetes_argocd_dispatch_command_is_exact_and_issue_scoped() -> None:
    assert "github.event.issue.number == 1705" in GATEWAY
    assert "github.event.comment.user.login == 'ericson-j-santos'" in GATEWAY
    assert "github.event.comment.body == '/reqsys run kubernetes-argocd-e2e-dev'" in GATEWAY
    assert "'/reqsys run kubernetes-argocd-e2e-dev')" in GATEWAY


def test_kubernetes_argocd_dispatch_maps_only_to_existing_ci_e2e_workflow() -> None:
    assert "target='ci-e2e-governado.yml'" in GATEWAY
    dispatch_allowlist = GATEWAY.split("case \"$TARGET_WORKFLOW\" in", maxsplit=1)[1].split("esac", maxsplit=1)[0]
    assert "runtime-e2e-continuous.yml" in dispatch_allowlist
    assert "ci-e2e-governado.yml" in dispatch_allowlist
    assert "pending-development-agent-pr-permission-watch.yml" in dispatch_allowlist
    assert 'gh workflow run "$TARGET_WORKFLOW"' in GATEWAY
    assert "--ref main" in GATEWAY


def test_kubernetes_argocd_dispatch_has_no_arbitrary_parameters_or_self_hosted_pickup() -> None:
    assert "-f workflow=" not in GATEWAY
    assert "-f namespace=" not in GATEWAY
    assert "-f sha=" not in GATEWAY
    assert "steps.route.outputs.target == 'ci-e2e-governado.yml'" not in GATEWAY


def test_gateway_keeps_exact_run_and_sha_validation_for_kubernetes_dispatch() -> None:
    assert "dispatched_run_id_mismatch" in GATEWAY
    assert "dispatched_run_url_mismatch" in GATEWAY
    assert "dispatched_run_sha_mismatch" in GATEWAY
    assert "dispatched_run_event_mismatch" in GATEWAY
    assert "EXPECTED_SHA: ${{ steps.main.outputs.sha }}" in GATEWAY
