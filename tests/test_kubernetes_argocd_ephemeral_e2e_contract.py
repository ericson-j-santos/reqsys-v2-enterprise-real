from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/ci-e2e-governado.yml").read_text(encoding="utf-8")
SCRIPT = (ROOT / "scripts/kubernetes_argocd_ephemeral_e2e.sh").read_text(encoding="utf-8")


def test_workflow_routes_kubernetes_gitops_scope_without_new_workflow() -> None:
    assert "run_kubernetes_gitops_e2e" in WORKFLOW
    assert "k8s/bootstrap/dev/**" in WORKFLOW
    assert "argocd/applications/reqsys-dev-bootstrap.yaml" in WORKFLOW
    assert "Kubernetes + Argo CD GitOps E2E" in WORKFLOW
    assert "bash scripts/kubernetes_argocd_ephemeral_e2e.sh" in WORKFLOW


def test_workflow_runs_kubernetes_e2e_only_when_router_selects_it() -> None:
    assert "if: needs.e2e-router.outputs.run_kubernetes_gitops_e2e == 'true'" in WORKFLOW
    assert "run_kubernetes_gitops_e2e=true" in WORKFLOW
    assert "Falha ao calcular diff do PR; Kubernetes E2E será executado por segurança." in WORKFLOW
    assert "Falha ao calcular diff do push; Kubernetes E2E será executado por segurança." in WORKFLOW


def test_kind_and_argocd_sources_are_pinned() -> None:
    assert 'KIND_VERSION="v0.33.0"' in SCRIPT
    assert 'KIND_BINARY_SHA256="aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d"' in SCRIPT
    assert 'ARGO_CD_VERSION="v3.5.3"' in SCRIPT
    assert 'ARGO_CD_COMMIT="c9c369efcc5b2a0bd720803f8d14a1c3eaddf579"' in SCRIPT
    assert "sha256sum -c -" in SCRIPT
    assert "argoproj/argo-cd/${ARGO_CD_COMMIT}/manifests/install.yaml" in SCRIPT
    assert "/master/" not in SCRIPT
    assert "/latest/" not in SCRIPT


def test_e2e_is_ephemeral_and_fails_closed() -> None:
    assert 'trap cleanup EXIT' in SCRIPT
    assert 'kind delete cluster --name "$CLUSTER_NAME"' in SCRIPT
    assert '--patch "{\\\"spec\\\":{\\\"source\\\":{\\\"targetRevision\\\":\\\"${EVALUATED_SHA}\\\"}}}"' in SCRIPT
    assert "AUTO_SYNC_MUST_REMAIN_DISABLED" in SCRIPT
    assert 'operation_phase" == "Failed"' in SCRIPT
    assert 'sync_status" == "Synced"' in SCRIPT
    assert 'health_status" == "Healthy"' in SCRIPT
    assert 'observed_revision" == "$EVALUATED_SHA"' in SCRIPT


def test_e2e_uses_independent_kubernetes_read_and_negative_controls() -> None:
    assert "kubectl -n \"$TARGET_NAMESPACE\" get configmap reqsys-gitops-bootstrap" in SCRIPT
    assert '[[ "$OBS_ENV" == "development" ]]' in SCRIPT
    assert '[[ "$OBS_NAMESPACE" == "$TARGET_NAMESPACE" ]]' in SCRIPT
    assert 'WORKLOAD_COUNT="$(kubectl -n "$TARGET_NAMESPACE" get deployment,statefulset,daemonset,job,cronjob' in SCRIPT
    assert "validate_kubernetes_gitops_bootstrap.py --self-test-negative" in SCRIPT
    assert '"production_touched": False' in SCRIPT


def test_evidence_is_bound_to_sha_and_correlation_id() -> None:
    assert 'evaluated_sha": sha' in SCRIPT
    assert 'observed_revision": sha' in SCRIPT
    assert 'correlation_id": os.environ["CORRELATION_ID"]' in SCRIPT
    assert "KUBERNETES_ARGOCD_E2E_OK" in SCRIPT

def test_evaluated_sha_is_explicit_and_not_github_reserved_sha() -> None:
    assert "GITHUB_SHA" not in SCRIPT
    assert ': "${EVALUATED_SHA:?EVALUATED_SHA obrigatorio}"' in SCRIPT
    assert "EVALUATED_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in WORKFLOW
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in WORKFLOW
    assert "GITHUB_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" not in WORKFLOW
    assert 'cat "$ARTIFACT_DIR/evidence.json"' in SCRIPT
