import argparse

from scripts.evaluate_runtime_executive_temporal_regression import evaluate


def args():
    return argparse.Namespace(
        window=5,
        min_availability=95.0,
        max_avg_latency_ms=2500.0,
        max_recent_failure_rate=0.2,
        score_drop_runs=3,
        block_on_score_drop=False,
    )


def test_zero_samples_fail_closed():
    report = evaluate(
        {
            "history": [],
            "summary": {
                "availability_percent": 0,
                "avg_latency_ms": None,
                "score_trend": "stable",
                "latency_trend": "stable",
                "failure_trend": "stable",
                "stability": "unknown",
            },
        },
        args(),
    )

    assert report["status"] == "blocked"
    assert report["production_blocked"] is True
    assert report["risk"] == "high"
    assert report["observed"]["samples"] == 0
    assert any(
        item["code"] == "insufficient_evidence" and item["severity"] == "critical"
        for item in report["violations"]
    )


def test_single_healthy_sample_can_pass():
    report = evaluate(
        {
            "history": [
                {
                    "failure_count": 0,
                    "executive_score": 100,
                    "avg_latency_ms": 100,
                }
            ],
            "summary": {
                "availability_percent": 100,
                "avg_latency_ms": 100,
                "score_trend": "stable",
                "latency_trend": "stable",
                "failure_trend": "stable",
                "stability": "stable",
            },
        },
        args(),
    )

    assert report["status"] == "passed"
    assert report["production_blocked"] is False
    assert report["risk"] == "low"
    assert report["violations"] == []
