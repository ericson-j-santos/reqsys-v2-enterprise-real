from __future__ import annotations

from scripts.evaluate_environment_promotion_capture import evaluate_capture

SHA = "abcdef123456"


def fly_state(**changes):
    value = {
        "contract": "fly-environment-state-capture",
        "environment": "dev",
        "expected_sha": SHA,
        "ready": True,
        "blocking_issues": [],
        "production_touched": False,
    }
    value.update(changes)
    return value


def runtime(**changes):
    value = {
        "contract": "public-runtime-smoke-readiness",
        "environment": "dev",
        "total": 4,
        "ok": 4,
        "readiness": {
            "api_ready": True,
            "runtime_ready": True,
            "blocking_issues": [],
        },
    }
    value.update(changes)
    return value


def publication(observed_sha: str = SHA):
    return {
        "contract": "publication-sync-validation",
        "ok": True,
        "environments": [
            {
                "environment": "dev",
                "expected": {"sha": SHA},
                "observed": {"sha": observed_sha},
                "synced": True,
                "blocking_issues": [],
            }
        ],
    }


def login(ready: bool = True):
    return {
        "contract": "multi-environment-login-validation",
        "ok": ready,
        "environments": [
            {
                "environment": "dev",
                "login_ready": ready,
                "errors": [] if ready else ["blocked"],
            }
        ],
    }


def evaluate(**changes):
    arguments = {
        "environment": "dev",
        "expected_sha": SHA,
        "fly_state": fly_state(),
        "runtime": runtime(),
        "publication": publication(),
        "login": login(),
        "observed_at_epoch": 1,
    }
    arguments.update(changes)
    return evaluate_capture(**arguments)


def test_all_evidence_allows_promotion() -> None:
    report = evaluate()
    assert report["ready"] is True
    assert report["automatic_promotion_allowed"] is True
    assert report["blocking_issues"] == []


def test_sha_mismatch_blocks_promotion() -> None:
    report = evaluate(publication=publication("111111111111"))
    assert report["ready"] is False
    assert "sha_consistency" in report["blocking_issues"]


def test_login_failure_blocks_promotion() -> None:
    report = evaluate(login=login(False))
    assert report["ready"] is False
    assert "login_ready" in report["blocking_issues"]


def test_missing_artifact_is_fail_closed() -> None:
    report = evaluate(fly_state={}, fly_state_error="artifact_missing")
    assert report["ready"] is False
    assert "fly_state_integrity" in report["blocking_issues"]
