import json
from pathlib import Path

import pytest

from scripts.evaluate_mutation_quality import evaluate_results, parse_results

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_ratchet_accepts_counts_at_the_baseline(tmp_path: Path) -> None:
    results = tmp_path / "mutation-results.txt"
    results.write_text(
        "app.core.alpha.x_one__mutmut_1: survived\n"
        "app.core.alpha.x_two__mutmut_1: no tests\n",
        encoding="utf-8",
    )
    policy = tmp_path / "policy.json"
    _write_json(policy, {"max_counts": {"survived": 1, "no tests": 1}})

    report = evaluate_results(results, policy)

    assert report["status"] == "passed"
    assert report["counts"]["survived"] == 1
    assert report["counts"]["no tests"] == 1
    assert report["violations"] == []


def test_ratchet_rejects_any_regression(tmp_path: Path) -> None:
    results = tmp_path / "mutation-results.txt"
    results.write_text(
        "app.core.alpha.x_one__mutmut_1: survived\n"
        "app.core.alpha.x_two__mutmut_1: survived\n",
        encoding="utf-8",
    )
    policy = tmp_path / "policy.json"
    _write_json(policy, {"max_counts": {"survived": 1}})

    report = evaluate_results(results, policy)

    assert report["status"] == "failed"
    assert report["violations"] == ["survived: observed=2 limit=1"]


def test_parser_rejects_unknown_mutmut_status(tmp_path: Path) -> None:
    results = tmp_path / "mutation-results.txt"
    results.write_text("app.core.alpha.x_one__mutmut_1: new status\n", encoding="utf-8")

    counts, malformed = parse_results(results)

    assert counts == {}
    assert malformed == ["line 1: unknown status 'new status'"]


def test_policy_rejects_invalid_limit(tmp_path: Path) -> None:
    results = tmp_path / "mutation-results.txt"
    results.write_text("", encoding="utf-8")
    policy = tmp_path / "policy.json"
    _write_json(policy, {"max_counts": {"survived": -1}})

    with pytest.raises(ValueError, match="non-negative integer"):
        evaluate_results(results, policy)


def test_versioned_policy_is_bound_to_the_verified_ci_baseline() -> None:
    policy = json.loads(
        (ROOT / "config" / "mutation-quality-policy.json").read_text(encoding="utf-8")
    )

    assert policy["tool_version"] == "3.8.0"
    assert policy["scope"] == "backend/app/core/*"
    assert policy["baseline"] == {
        "source_run_id": 39962908518,
        "source_sha": "4fa7f66e387c806ccfc73a3c196fc703af829398",
    }
    assert policy["max_counts"] == {
        "survived": 591,
        "no tests": 5827,
        "timeout": 0,
        "suspicious": 0,
    }
