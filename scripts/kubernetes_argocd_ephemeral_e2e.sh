#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_SHA:?GITHUB_SHA obrigatorio}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID obrigatorio}"

KIND_VERSION="v0.33.0"
KIND_BINARY_SHA256="aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d"
ARGO_CD_VERSION="v3.5.3"
ARGO_CD_COMMIT="c9c369efcc5b2a0bd720803f8d14a1c3eaddf579"
CLUSTER_NAME="reqsys-gitops-e2e"
APPLICATION_NAME="reqsys-dev-bootstrap"
ARGO_NAMESPACE="argocd"
TARGET_NAMESPACE="reqsys-dev"
ARTIFACT_DIR="artifacts/kubernetes-gitops-e2e"
CORRELATION_ID="k8s-argocd-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT:-1}"
TMP_DIR="$(mktemp -d)"

mkdir -p "$ARTIFACT_DIR"

write_failure_evidence() {
  local exit_code="$1"
  python3 - "$ARTIFACT_DIR/evidence.json" "$exit_code" "$CORRELATION_ID" "$GITHUB_SHA" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path, code, correlation_id, sha = sys.argv[1:]
payload = {
    "schema_version": "1.0.0",
    "status": "failed",
    "environment": "development",
    "runtime": "kind-ephemeral-ci",
    "evaluated_sha": sha,
    "correlation_id": correlation_id,
    "exit_code": int(code),
    "production_touched": False,
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
}
Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

cleanup() {
  local exit_code=$?
  trap - EXIT
  if [[ "$exit_code" -ne 0 ]]; then
    {
      echo "=== cluster ==="
      kubectl cluster-info || true
      echo "=== argocd pods ==="
      kubectl -n "$ARGO_NAMESPACE" get pods -o wide || true
      echo "=== application ==="
      kubectl -n "$ARGO_NAMESPACE" get application "$APPLICATION_NAME" -o wide || true
      echo "=== target namespace ==="
      kubectl -n "$TARGET_NAMESPACE" get all,configmap || true
    } > "$ARTIFACT_DIR/diagnostics.txt" 2>&1 || true
    write_failure_evidence "$exit_code"
  fi
  if command -v kind >/dev/null 2>&1; then
    kind delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
  exit "$exit_code"
}
trap cleanup EXIT

for command_name in curl docker kubectl python3 sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || {
    echo "Dependencia ausente: $command_name" >&2
    exit 10
  }
done

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "Arquitetura nao suportada por este E2E: $(uname -m)" >&2
  exit 11
fi

curl -fsSL --retry 4 --retry-all-errors --retry-delay 2 \
  -o "$TMP_DIR/kind" \
  "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-amd64"
echo "${KIND_BINARY_SHA256}  ${TMP_DIR}/kind" | sha256sum -c -
chmod +x "$TMP_DIR/kind"
export PATH="$TMP_DIR:$PATH"

kind create cluster --name "$CLUSTER_NAME" --wait 120s
kubectl wait --for=condition=Ready node --all --timeout=120s

python scripts/validate_kubernetes_gitops_bootstrap.py
python scripts/validate_kubernetes_gitops_bootstrap.py --self-test-negative

ARGO_INSTALL_MANIFEST="$TMP_DIR/argocd-install.yaml"
curl -fsSL --retry 4 --retry-all-errors --retry-delay 2 \
  -o "$ARGO_INSTALL_MANIFEST" \
  "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGO_CD_COMMIT}/manifests/install.yaml"
test -s "$ARGO_INSTALL_MANIFEST"
kubectl create namespace "$ARGO_NAMESPACE"
kubectl apply -n "$ARGO_NAMESPACE" --server-side --force-conflicts -f "$ARGO_INSTALL_MANIFEST"
kubectl wait --for=condition=Established crd/applications.argoproj.io --timeout=120s
kubectl -n "$ARGO_NAMESPACE" wait --for=condition=Available deployment --all --timeout=300s
kubectl -n "$ARGO_NAMESPACE" rollout status statefulset/argocd-application-controller --timeout=300s

kubectl apply -f argocd/applications/reqsys-dev-bootstrap.yaml
kubectl -n "$ARGO_NAMESPACE" patch application "$APPLICATION_NAME" --type merge \
  --patch "{\"spec\":{\"source\":{\"targetRevision\":\"${GITHUB_SHA}\"}}}"

kubectl -n "$ARGO_NAMESPACE" get application "$APPLICATION_NAME" -o json > "$TMP_DIR/application.json"
python3 - "$TMP_DIR/application.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
sync_policy = payload.get("spec", {}).get("syncPolicy", {})
if "automated" in sync_policy:
    raise SystemExit("AUTO_SYNC_MUST_REMAIN_DISABLED")
PY

kubectl -n "$ARGO_NAMESPACE" patch application "$APPLICATION_NAME" --type merge \
  --patch "{\"operation\":{\"sync\":{\"revision\":\"${GITHUB_SHA}\",\"prune\":false,\"syncOptions\":[\"CreateNamespace=true\"]}}}"

synced=false
for _ in $(seq 1 72); do
  sync_status="$(kubectl -n "$ARGO_NAMESPACE" get application "$APPLICATION_NAME" -o jsonpath='{.status.sync.status}' 2>/dev/null || true)"
  health_status="$(kubectl -n "$ARGO_NAMESPACE" get application "$APPLICATION_NAME" -o jsonpath='{.status.health.status}' 2>/dev/null || true)"
  observed_revision="$(kubectl -n "$ARGO_NAMESPACE" get application "$APPLICATION_NAME" -o jsonpath='{.status.sync.revision}' 2>/dev/null || true)"
  operation_phase="$(kubectl -n "$ARGO_NAMESPACE" get application "$APPLICATION_NAME" -o jsonpath='{.status.operationState.phase}' 2>/dev/null || true)"
  if [[ "$operation_phase" == "Failed" || "$operation_phase" == "Error" ]]; then
    echo "Argo CD sync falhou: phase=$operation_phase" >&2
    exit 20
  fi
  if [[ "$sync_status" == "Synced" && "$health_status" == "Healthy" && "$observed_revision" == "$GITHUB_SHA" && "$operation_phase" == "Succeeded" ]]; then
    synced=true
    break
  fi
  sleep 5
done
[[ "$synced" == "true" ]] || {
  echo "Timeout aguardando Argo CD Synced/Healthy no SHA $GITHUB_SHA" >&2
  exit 21
}

OBS_ENV="$(kubectl -n "$TARGET_NAMESPACE" get configmap reqsys-gitops-bootstrap -o jsonpath='{.data.environment}')"
OBS_NAMESPACE="$(kubectl -n "$TARGET_NAMESPACE" get configmap reqsys-gitops-bootstrap -o jsonpath='{.data.expected_namespace}')"
OBS_PURPOSE="$(kubectl -n "$TARGET_NAMESPACE" get configmap reqsys-gitops-bootstrap -o jsonpath='{.data.purpose}')"
[[ "$OBS_ENV" == "development" ]]
[[ "$OBS_NAMESPACE" == "$TARGET_NAMESPACE" ]]
[[ "$OBS_PURPOSE" == "gitops-bootstrap-canary" ]]

WORKLOAD_COUNT="$(kubectl -n "$TARGET_NAMESPACE" get deployment,statefulset,daemonset,job,cronjob -o name --ignore-not-found | wc -l | tr -d ' ')"
[[ "$WORKLOAD_COUNT" == "0" ]] || {
  echo "Bootstrap criou workload inesperado: $WORKLOAD_COUNT" >&2
  exit 22
}

KUBERNETES_VERSION="$(kubectl version -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["serverVersion"]["gitVersion"])')"
export OBS_ENV OBS_NAMESPACE OBS_PURPOSE KUBERNETES_VERSION ARGO_CD_VERSION ARGO_CD_COMMIT CORRELATION_ID
python3 - "$ARTIFACT_DIR/evidence.json" "$GITHUB_SHA" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path, sha = sys.argv[1:]
payload = {
    "schema_version": "1.0.0",
    "status": "passed",
    "environment": "development",
    "runtime": "kind-ephemeral-ci",
    "evaluated_sha": sha,
    "argocd": {
        "version": os.environ["ARGO_CD_VERSION"],
        "source_commit": os.environ["ARGO_CD_COMMIT"],
        "application": "reqsys-dev-bootstrap",
        "sync_status": "Synced",
        "health_status": "Healthy",
        "observed_revision": sha,
    },
    "kubernetes": {
        "version": os.environ["KUBERNETES_VERSION"],
        "namespace": os.environ["OBS_NAMESPACE"],
        "configmap_environment": os.environ["OBS_ENV"],
        "configmap_purpose": os.environ["OBS_PURPOSE"],
        "business_workloads_created": 0,
    },
    "correlation_id": os.environ["CORRELATION_ID"],
    "production_touched": False,
    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
}
Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "KUBERNETES_ARGOCD_E2E_OK sha=$GITHUB_SHA correlation_id=$CORRELATION_ID"
