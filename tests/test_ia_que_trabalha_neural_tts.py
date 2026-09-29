from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts" / "ia_que_trabalha_neural_tts.py"
VALIDATOR = ROOT / "scripts" / "validate_ia_que_trabalha_neural_tts.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ia-que-trabalha-neural-tts.yml"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_narration_contract_preserves_ten_timed_segments() -> None:
    module = _load(GENERATOR, "tts_generator")
    assert len(module.SEGMENTS) == 10
    assert module.SEGMENTS[0]["end_s"] <= 2.0
    assert module.SEGMENTS[-1]["end_s"] <= 28.7
    assert all(item["start_s"] < item["end_s"] for item in module.SEGMENTS)
    assert module.KOKORO_VOICES == ("pf_dora", "pm_alex")
    assert module.PIPER_VOICES == ("pt_BR-cadu-medium", "pt_BR-faber-medium")


def test_generator_has_zero_cost_and_fail_closed_markers() -> None:
    raw = GENERATOR.read_text(encoding="utf-8")
    assert "GENERATE-IA-QUE-TRABALHA-NEURAL-TTS" in raw
    assert '"paid_service": False' in raw
    assert '"production_touched": False' in raw
    assert '"secrets_read": False' in raw
    for forbidden in ("elevenlabs", "azure.cognitiveservices", "openai.com/v1/audio"):
        assert forbidden not in raw.lower()


def test_workflow_uses_governed_session_and_gateway_only() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "work/ia-que-trabalha-neural-tts-20260928" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "session_launcher.py" in raw
    assert "SESSION_LAUNCH_OK" in raw
    assert "command_gateway.py" in raw
    assert '"--risk", "1"' in raw
    assert '"--risk", "2"' in raw
    assert "actions/upload-artifact@" in raw
    assert "push:" in raw
    assert "branches:" in raw
    assert "      - main" not in raw
    assert "secrets." not in raw


def test_validator_rejects_missing_evidence(tmp_path: Path) -> None:
    module = _load(VALIDATOR, "tts_validator")
    errors = module.validate_evidence(tmp_path / "missing.json", tmp_path, "a" * 40)
    assert errors == ["evidence_missing"]


def test_validator_rejects_false_positive_payload(tmp_path: Path) -> None:
    module = _load(VALIDATOR, "tts_validator_negative")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "ok": True,
                "host": "NOTERI",
                "expected_sha": "b" * 40,
                "observed_sha": "b" * 40,
                "paid_service": False,
                "production_touched": False,
                "secrets_read": False,
                "segments_expected": 10,
                "voices": ["fake-a", "fake-b"],
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    errors = module.validate_evidence(evidence, tmp_path, "b" * 40)
    assert any(item.startswith("file_count_mismatch") for item in errors)
    assert "voice_segment_matrix_incomplete" in errors


def run_all() -> None:
    import tempfile

    test_narration_contract_preserves_ten_timed_segments()
    test_generator_has_zero_cost_and_fail_closed_markers()
    test_workflow_uses_governed_session_and_gateway_only()
    with tempfile.TemporaryDirectory() as raw:
        test_validator_rejects_missing_evidence(Path(raw))
    with tempfile.TemporaryDirectory() as raw:
        test_validator_rejects_false_positive_payload(Path(raw))


if __name__ == "__main__":
    run_all()
    print("IA_QUE_TRABALHA_TTS_CONTRACT_OK")
