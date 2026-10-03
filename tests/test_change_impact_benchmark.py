import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "change_impact_benchmark.py"
DATASET = ROOT / "data" / "change-impact" / "historical-ground-truth-v1.json"


def test_benchmark_script_runs_end_to_end_without_llm(tmp_path):
    output = tmp_path / "benchmark.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dataset",
            str(DATASET),
            "--output",
            str(output),
            "--llm-mode",
            "disabled",
            "--correlation-id",
            "change-impact-e2e-test",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["correlation_id"] == "change-impact-e2e-test"
    assert payload["llm_mode"] == "disabled"
    assert payload["llm_used_for_all_cases"] is False
    assert payload["aggregate"]["graph"]["mean_recall"] == 1.0
    assert payload["aggregate"]["graph"]["mean_precision"] == 1.0
    assert len(payload["cases"]) == 6
    hybrid = [
        row
        for row in payload["cases"]
        if row["strategy"] == "hybrid_rag_llm"
    ]
    assert hybrid
    assert all(row["llm_status"] == "disabled" for row in hybrid)


def test_benchmark_script_rejects_invalid_dataset_without_output(tmp_path):
    dataset = tmp_path / "invalid.json"
    output = tmp_path / "benchmark.json"
    dataset.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "artifact_id": "REQ-1",
                        "kind": "REQUIREMENT",
                        "text": "texto",
                        "source_uri": "req.md",
                        "links": [],
                    }
                ],
                "changes": [
                    {
                        "change_id": "CHANGE-1",
                        "query": "mudança",
                        "seed_artifact_ids": ["REQ-1"],
                        "ground_truth": ["UNKNOWN"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dataset",
            str(dataset),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert completed.returncode == 2
    assert "CHANGE_IMPACT_BENCHMARK_FAILED" in completed.stderr
    assert not output.exists()
