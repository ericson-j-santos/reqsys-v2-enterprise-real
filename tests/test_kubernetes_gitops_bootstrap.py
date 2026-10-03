from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from scripts.validate_kubernetes_gitops_bootstrap import (
    APPLICATION_PATH,
    BOOTSTRAP_DIR,
    KUSTOMIZATION_PATH,
    load_yaml,
    self_test_negative,
    validate_documents,
    validate_repository,
)


ROOT = Path(__file__).resolve().parents[1]


def _documents():
    application = load_yaml(ROOT / APPLICATION_PATH)
    kustomization = load_yaml(ROOT / KUSTOMIZATION_PATH)
    configmap = load_yaml(ROOT / BOOTSTRAP_DIR / "configmap.yaml")
    return application, kustomization, configmap


def test_repository_bootstrap_contract_passes() -> None:
    result = validate_repository(ROOT)

    assert result.status == "passed"
    assert result.errors == []


def test_auto_sync_is_blocked_before_real_e2e() -> None:
    application, kustomization, configmap = _documents()
    application = deepcopy(application)
    application["spec"]["syncPolicy"]["automated"] = {"prune": True, "selfHeal": True}

    result = validate_documents(application, kustomization, [configmap])

    assert result.status == "blocked"
    assert "ARGO_AUTOSYNC_BLOCKED_UNTIL_REAL_E2E" in result.errors


def test_bootstrap_rejects_secret_resource() -> None:
    application, kustomization, _ = _documents()
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "forbidden"},
        "stringData": {"token": "not-a-real-secret"},
    }

    result = validate_documents(application, kustomization, [secret])

    assert result.status == "blocked"
    assert "BOOTSTRAP_KIND_FORBIDDEN:Secret" in result.errors


def test_bootstrap_rejects_non_dev_namespace() -> None:
    application, kustomization, configmap = _documents()
    application = deepcopy(application)
    application["spec"]["destination"]["namespace"] = "reqsys-prod"

    result = validate_documents(application, kustomization, [configmap])

    assert result.status == "blocked"
    assert "ARGO_DESTINATION_MUST_BE_DEV" in result.errors


def test_validation_is_idempotent() -> None:
    first = validate_repository(ROOT)
    second = validate_repository(ROOT)

    assert first == second


def test_negative_self_test_detects_known_failures() -> None:
    assert self_test_negative(ROOT) is True
