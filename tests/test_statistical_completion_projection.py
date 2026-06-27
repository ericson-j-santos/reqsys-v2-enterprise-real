"""Testes do builder Statistical Completion Projection.

Os testes cobrem o contrato governado:
- presenca dos campos obrigatorios do schema;
- determinismo do payload quando ``REQSYS_PROJECTION_GENERATED_AT`` esta definido;
- consistencia entre JSON e markdown gerados;
- soma e ordenacao dos campos numericos para evitar regressao silenciosa.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.statistical_completion_projection import (  # noqa: E402
    SCHEMA_VERSION,
    build_projection,
    render_markdown,
    write_outputs,
)


SCHEMA_PATH = ROOT_DIR / "docs" / "contracts" / "statistical-completion-projection.schema.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_payload_contains_required_top_level_fields() -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    schema = _load_schema()
    for field in schema["required"]:
        assert field in payload, f"Campo obrigatorio ausente no payload: {field}"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["mode"] == "report_only"
    assert payload["status"] in {"stable", "em_consolidacao", "atencao", "risco"}


def test_payload_is_deterministic_with_env_override(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_PROJECTION_GENERATED_AT", "2026-06-27T03:00:00Z")
    payload_a = build_projection()
    payload_b = build_projection()
    assert payload_a == payload_b
    assert payload_a["generated_at"] == "2026-06-27T03:00:00Z"


def test_velocity_ranges_are_consistent() -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    velocity = payload["velocity"]
    for key in (
        "prs_per_business_day",
        "green_merges_per_day",
        "ci_fixes_per_cycle",
        "safe_parallel_increments",
        "lead_time_minutes",
    ):
        bounds = velocity[key]
        assert bounds["min"] <= bounds["max"], f"Range invertido em {key}"
    assert 0 <= velocity["ci_stabilization_rate_percent"] <= 100


def test_timeline_milestone_ranges_are_consistent() -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    for scenario in ("conservative", "accelerated"):
        milestones = payload["timelines"][scenario]["milestones"]
        assert milestones, f"Cenario {scenario} precisa ter marcos"
        for milestone in milestones:
            assert milestone["min_days"] <= milestone["max_days"], (
                f"Marco com range invertido em {scenario}: {milestone}"
            )


def test_completion_and_gaps_are_percentages() -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    for row in payload["completion_percent"]:
        assert 0 <= row["percent"] <= 100
    for row in payload["remaining_gaps_percent"]:
        assert 0 <= row["gap_percent"] <= 100
    for row in payload["final_probability_percent"]:
        assert 0 <= row["probability_percent"] <= 100


def test_bottlenecks_and_levers_are_ranked_in_sequence() -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    bottleneck_ranks = [item["rank"] for item in payload["bottlenecks"]]
    lever_ranks = [item["rank"] for item in payload["acceleration_levers"]]
    assert bottleneck_ranks == list(range(1, len(bottleneck_ranks) + 1))
    assert lever_ranks == list(range(1, len(lever_ranks) + 1))


def test_render_markdown_contains_section_headers() -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    rendered = render_markdown(payload)
    expected_sections = [
        "# Projecao Estatistica de Conclusao - ReqSys",
        "## Leitura executiva",
        "## Estado atual consolidado",
        "## Velocidade atual observada",
        "## Percentual real de conclusao",
        "## Quanto falta",
        "## Cenario conservador",
        "## Cenario acelerado (recomendado)",
        "## Gargalos principais",
        "## Indice estatistico de risco",
        "## Tendencia atual",
        "## Estimativa realista final",
        "## O que mais acelera agora",
    ]
    for section in expected_sections:
        assert section in rendered, f"Secao ausente no markdown: {section}"


def test_write_outputs_generates_json_and_markdown(tmp_path) -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    json_path, markdown_path = write_outputs(payload, tmp_path)
    assert json_path.exists()
    assert markdown_path.exists()
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed == payload
    rendered_text = markdown_path.read_text(encoding="utf-8")
    assert rendered_text.startswith("# Projecao Estatistica de Conclusao - ReqSys")


def test_payload_matches_schema_enums_for_status_and_levels() -> None:
    payload = build_projection(generated_at="2026-06-27T03:00:00Z")
    schema = _load_schema()
    allowed_status = schema["properties"]["status"]["enum"]
    allowed_modes = schema["properties"]["mode"]["enum"]
    allowed_risk_levels = schema["properties"]["risks"]["items"]["properties"]["level"]["enum"]
    allowed_maturities = schema["properties"]["current_state"]["items"]["properties"]["maturity"]["enum"]
    allowed_trend_directions = schema["properties"]["trends"]["items"]["properties"]["direction"]["enum"]
    allowed_trend_intensity = schema["properties"]["trends"]["items"]["properties"]["intensity"]["enum"]
    assert payload["status"] in allowed_status
    assert payload["mode"] in allowed_modes
    for risk in payload["risks"]:
        assert risk["level"] in allowed_risk_levels
    for state in payload["current_state"]:
        assert state["maturity"] in allowed_maturities
    for trend in payload["trends"]:
        assert trend["direction"] in allowed_trend_directions
        assert trend["intensity"] in allowed_trend_intensity
