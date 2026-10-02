import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "classify_public_access_runtime_scope.py"
SPEC = importlib.util.spec_from_file_location("public_access_runtime_scope", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
classify_paths = MODULE.classify_paths


def _classify(paths: list[str], *, scope_available: bool = True) -> dict[str, object]:
    return classify_paths(
        paths,
        scope_available=scope_available,
        event_name="push",
        base_sha="a" * 40,
        head_sha="b" * 40,
    )


def test_ci_sdd_explicit_test_roots_and_docs_do_not_require_runtime_sha_match() -> None:
    result = _classify(
        [
            ".github/workflows/noteri-desktop-network-probe.yml",
            ".sdd/specs/noteri-desktop-network-probe.spec.json",
            "tests/test_noteri_desktop_orchestrator_status_probe.py",
            "backend/tests/test_runtime_contract.py",
            "backend/ocr_tests/test_runtime_contract.py",
            "docs/runbooks/runtime-public-access-readiness.md",
        ]
    )

    assert result["runtime_sha_required"] is False
    assert result["decision_reason"] == "ci_sdd_test_or_docs_only"
    assert result["runtime_or_unknown_paths"] == []


def test_nested_test_named_paths_inside_build_context_remain_runtime() -> None:
    result = _classify(
        [
            "backend/app/fixtures/runtime_policy.json",
            "frontend/src/__tests__/runtimeBootstrap.js",
            "frontend/src/services/api.test.js",
        ]
    )

    assert result["runtime_sha_required"] is True
    assert result["decision_reason"] == "runtime_or_unknown_path_changed"
    assert result["runtime_or_unknown_paths"] == [
        "backend/app/fixtures/runtime_policy.json",
        "frontend/src/__tests__/runtimeBootstrap.js",
        "frontend/src/services/api.test.js",
    ]


def test_case_variant_of_allowlisted_root_fails_closed() -> None:
    result = _classify(["Docs/runtime.py", "backend/Tests/runtime_policy.py"])

    assert result["runtime_sha_required"] is True
    assert result["runtime_or_unknown_paths"] == [
        "Docs/runtime.py",
        "backend/Tests/runtime_policy.py",
    ]


def test_runtime_change_keeps_exact_sha_requirement() -> None:
    result = _classify(["backend/app/main.py", "docs/VALIDACAO_ANALITICA_ACESSOS.md"])

    assert result["runtime_sha_required"] is True
    assert result["decision_reason"] == "runtime_or_unknown_path_changed"
    assert result["runtime_or_unknown_paths"] == ["backend/app/main.py"]


def test_runtime_configuration_change_keeps_exact_sha_requirement() -> None:
    result = _classify(["docker-compose.pc24x7-public-dev.yml"])

    assert result["runtime_sha_required"] is True
    assert result["runtime_or_unknown_paths"] == ["docker-compose.pc24x7-public-dev.yml"]


def test_runtime_markdown_and_test_named_public_assets_are_not_allowlisted() -> None:
    result = _classify(
        [
            "backend/app/prompts/system.md",
            "frontend/public/help.md",
            "frontend/public/demo.test.js",
        ]
    )

    assert result["runtime_sha_required"] is True
    assert result["runtime_or_unknown_paths"] == [
        "backend/app/prompts/system.md",
        "frontend/public/demo.test.js",
        "frontend/public/help.md",
    ]


def test_cumulative_runtime_drift_is_blocking_even_after_ci_only_merge() -> None:
    result = _classify(
        [
            ".github/workflows/noteri-control-plane-probe.yml",
            ".sdd/specs/noteri-control-plane-fallback.spec.json",
            "tests/test_noteri_control_plane_fallback.py",
            "frontend/package-lock.json",
            "frontend/package.json",
            "frontend/src/main.js",
            "frontend/src/services/publicRuntimeLocator.js",
            "frontend/src/views/LoginView.vue",
        ]
    )

    assert result["runtime_sha_required"] is True
    assert result["runtime_or_unknown_paths"] == [
        "frontend/package-lock.json",
        "frontend/package.json",
        "frontend/src/main.js",
        "frontend/src/services/publicRuntimeLocator.js",
        "frontend/src/views/LoginView.vue",
    ]


def test_unknown_path_fails_closed() -> None:
    result = _classify(["unknown-surface/config.json"])

    assert result["runtime_sha_required"] is True
    assert result["decision_reason"] == "runtime_or_unknown_path_changed"


def test_invalid_relative_path_fails_closed() -> None:
    result = _classify(["../backend/app/main.py"])

    assert result["runtime_sha_required"] is True
    assert result["runtime_or_unknown_paths"] == ["invalid:../backend/app/main.py"]


def test_missing_or_empty_scope_fails_closed() -> None:
    unavailable = _classify([], scope_available=False)
    empty = _classify([])

    assert unavailable["runtime_sha_required"] is True
    assert unavailable["decision_reason"] == "change_scope_unavailable_fail_closed"
    assert empty["runtime_sha_required"] is True
    assert empty["decision_reason"] == "empty_change_scope_fail_closed"
