from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_mutmut_configuration_keeps_the_golden_test_focused() -> None:
    config = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))

    mutmut = config["tool"]["mutmut"]
    assert mutmut["source_paths"] == ["app"]
    assert mutmut["only_mutate"] == ["app/core/*"]
    selection = mutmut["pytest_add_cli_args_test_selection"]
    assert selection[0] == "tests"
    assert set(selection[1:]) == {
        f"--ignore=tests/{name}"
        for name in (
            "test_change_impact_analysis.py",
            "test_cofre_runtime_evidence_script.py",
            "test_copilot_hitl_agent_network_blueprint.py",
            "test_generated_minimum_controlled_version_manifest.py",
            "test_lowcode_teams_notification_profile.py",
            "test_materialize_copilot_hitl_solution.py",
            "test_operational_observability_hub.py",
            "test_operational_orchestrator.py",
            "test_performance_slo_observability_integration.py",
            "test_resolve_lifecycle_requirement_codes.py",
            "test_trilha_e_arquitetura_viva.py",
            "test_wsjf_excel_workbook_api.py",
            "test_wsjf_workbook_package.py",
        )
    }
    assert mutmut["pytest_add_cli_args"] == ["-o", "pythonpath=../.."]
    assert mutmut["also_copy"] == [
        "copilot_memory_core",
        "copilot_memory_powerautomate_complete.py",
        "copilot_memory_simple_package.py",
        "data",
        "diagram_generator_portable",
        "ocr_evidencia",
        "token_broker",
        "wsjf_workbook_package.py",
    ]
    assert all((ROOT / "backend" / path).exists() for path in mutmut["also_copy"])
    assert all(
        "parents[2]" in (ROOT / "backend" / option.removeprefix("--ignore=")).read_text(
            encoding="utf-8"
        )
        for option in selection[1:]
    )


def test_golden_test_uses_the_pinned_mutmut_3_cli() -> None:
    workflow = (ROOT / ".github" / "workflows" / "golden-test-advanced.yml").read_text(
        encoding="utf-8"
    )

    assert "'mutmut==3.8.0'" in workflow
    assert "mutmut run\n" in workflow
    assert "evaluate_mutation_quality.py" in workflow
    assert "mutation-quality-summary.json" in workflow
    assert "grep -c 'survived'" not in workflow
    assert "--paths-to-mutate" not in workflow
    assert "--tests-dir" not in workflow
    assert "--runner" not in workflow
