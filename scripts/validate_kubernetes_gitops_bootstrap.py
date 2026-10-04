#!/usr/bin/env python3
"""Valida o bootstrap GitOps DEV de Kubernetes + Argo CD.

O primeiro incremento e deliberadamente fail-closed: ele permite somente um
ConfigMap canario em reqsys-dev e proibe auto-sync enquanto o E2E real do
cluster ainda nao foi comprovado.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_URL = "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real.git"
APPLICATION_PATH = Path("argocd/applications/reqsys-dev-bootstrap.yaml")
KUSTOMIZATION_PATH = Path("k8s/bootstrap/dev/kustomization.yaml")
BOOTSTRAP_DIR = Path("k8s/bootstrap/dev")
EXPECTED_NAMESPACE = "reqsys-dev"
FORBIDDEN_KINDS = {
    "Secret",
    "ExternalSecret",
    "SealedSecret",
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "Job",
    "CronJob",
}


@dataclass(frozen=True)
class ValidationResult:
    status: str
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": "1.0.0", "status": self.status, "errors": self.errors}


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML deve conter objeto na raiz: {path}")
    return payload


def _nested(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def validate_documents(
    application: dict[str, Any],
    kustomization: dict[str, Any],
    resources: list[dict[str, Any]],
) -> ValidationResult:
    errors: list[str] = []

    if application.get("apiVersion") != "argoproj.io/v1alpha1" or application.get("kind") != "Application":
        errors.append("ARGO_APPLICATION_CONTRACT_INVALID")

    if _nested(application, "metadata", "namespace") != "argocd":
        errors.append("ARGO_CONTROL_NAMESPACE_INVALID")
    if _nested(application, "spec", "source", "repoURL") != REPOSITORY_URL:
        errors.append("ARGO_SOURCE_REPOSITORY_INVALID")
    if _nested(application, "spec", "source", "targetRevision") != "main":
        errors.append("ARGO_TARGET_REVISION_MUST_BE_MAIN")
    if _nested(application, "spec", "source", "path") != BOOTSTRAP_DIR.as_posix():
        errors.append("ARGO_SOURCE_PATH_INVALID")
    if _nested(application, "spec", "destination", "server") != "https://kubernetes.default.svc":
        errors.append("ARGO_DESTINATION_SERVER_INVALID")
    if _nested(application, "spec", "destination", "namespace") != EXPECTED_NAMESPACE:
        errors.append("ARGO_DESTINATION_MUST_BE_DEV")

    sync_policy = _nested(application, "spec", "syncPolicy")
    if not isinstance(sync_policy, dict):
        errors.append("ARGO_SYNC_POLICY_MISSING")
        sync_policy = {}
    if "automated" in sync_policy:
        errors.append("ARGO_AUTOSYNC_BLOCKED_UNTIL_REAL_E2E")

    sync_options = sync_policy.get("syncOptions")
    if not isinstance(sync_options, list) or "CreateNamespace=true" not in sync_options:
        errors.append("ARGO_CREATE_NAMESPACE_REQUIRED")

    if kustomization.get("apiVersion") != "kustomize.config.k8s.io/v1beta1" or kustomization.get("kind") != "Kustomization":
        errors.append("KUSTOMIZATION_CONTRACT_INVALID")
    if kustomization.get("namespace") != EXPECTED_NAMESPACE:
        errors.append("KUSTOMIZATION_NAMESPACE_MUST_BE_DEV")
    if kustomization.get("resources") != ["configmap.yaml"]:
        errors.append("BOOTSTRAP_RESOURCES_MUST_BE_CANARY_ONLY")

    if len(resources) != 1:
        errors.append("BOOTSTRAP_RESOURCE_COUNT_INVALID")

    for resource in resources:
        kind = str(resource.get("kind") or "")
        if kind in FORBIDDEN_KINDS:
            errors.append(f"BOOTSTRAP_KIND_FORBIDDEN:{kind}")
        if kind != "ConfigMap":
            errors.append(f"BOOTSTRAP_ONLY_CONFIGMAP_ALLOWED:{kind or 'missing'}")
            continue

        if _nested(resource, "metadata", "name") != "reqsys-gitops-bootstrap":
            errors.append("BOOTSTRAP_CONFIGMAP_NAME_INVALID")
        if _nested(resource, "metadata", "labels", "reqsys.io/environment") != "development":
            errors.append("BOOTSTRAP_ENVIRONMENT_LABEL_INVALID")
        if _nested(resource, "metadata", "annotations", "argocd.argoproj.io/sync-options") != "Prune=confirm":
            errors.append("BOOTSTRAP_PRUNE_CONFIRM_REQUIRED")
        if _nested(resource, "data", "environment") != "development":
            errors.append("BOOTSTRAP_DATA_ENVIRONMENT_INVALID")
        if _nested(resource, "data", "expected_namespace") != EXPECTED_NAMESPACE:
            errors.append("BOOTSTRAP_EXPECTED_NAMESPACE_INVALID")

    return ValidationResult(status="passed" if not errors else "blocked", errors=sorted(set(errors)))


def validate_repository(root: Path) -> ValidationResult:
    application = load_yaml(root / APPLICATION_PATH)
    kustomization = load_yaml(root / KUSTOMIZATION_PATH)
    resources_field = kustomization.get("resources")
    if not isinstance(resources_field, list):
        return ValidationResult(status="blocked", errors=["KUSTOMIZATION_RESOURCES_INVALID"])

    resources: list[dict[str, Any]] = []
    expected_root = (root / BOOTSTRAP_DIR).resolve()
    for relative in resources_field:
        candidate = (expected_root / str(relative)).resolve()
        if candidate.parent != expected_root:
            return ValidationResult(status="blocked", errors=["BOOTSTRAP_RESOURCE_PATH_INVALID"])
        resources.append(load_yaml(candidate))

    return validate_documents(application, kustomization, resources)


def self_test_negative(root: Path) -> bool:
    application = load_yaml(root / APPLICATION_PATH)
    kustomization = load_yaml(root / KUSTOMIZATION_PATH)
    configmap = load_yaml(root / BOOTSTRAP_DIR / "configmap.yaml")

    bad_application = deepcopy(application)
    bad_application["spec"]["syncPolicy"]["automated"] = {"prune": True, "selfHeal": True}
    auto_sync = validate_documents(bad_application, kustomization, [configmap])

    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "forbidden"},
        "stringData": {"token": "never-store-secrets-here"},
    }
    secret_check = validate_documents(application, kustomization, [secret])

    prod_application = deepcopy(application)
    prod_application["spec"]["destination"]["namespace"] = "reqsys-prod"
    prod = validate_documents(prod_application, kustomization, [configmap])

    return (
        "ARGO_AUTOSYNC_BLOCKED_UNTIL_REAL_E2E" in auto_sync.errors
        and any(item.startswith("BOOTSTRAP_KIND_FORBIDDEN:Secret") for item in secret_check.errors)
        and "ARGO_DESTINATION_MUST_BE_DEV" in prod.errors
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida bootstrap Kubernetes/Argo CD restrito a DEV")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--self-test-negative", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if args.self_test_negative:
        ok = self_test_negative(root)
        print(json.dumps({"self_test_negative": ok}, sort_keys=True))
        return 0 if ok else 2

    result = validate_repository(root)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
