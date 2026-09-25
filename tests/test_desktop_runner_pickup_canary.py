from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import desktop_runner_pickup_canary as subject


def test_canary_rejects_wrong_host(tmp_path: Path) -> None:
    with pytest.raises(subject.CanaryError, match="wrong_host"):
        subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "evidence.json",
            host="OTHER-HOST",
            platform="nt",
        )


def test_canary_requires_exact_runner_and_sha(tmp_path: Path) -> None:
    env = {
        "RUNNER_NAME": subject.TARGET_HOST,
        "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
        "GITHUB_SHA": "a" * 40,
    }
    with patch.dict(subject.os.environ, env, clear=False):
        result = subject.execute(
            confirm=subject.CONFIRM,
            evidence_file=tmp_path / "evidence.json",
            host=subject.TARGET_HOST,
            platform="nt",
        )
    assert result["result"] == "DESKTOP_GITHUB_RUNNER_PICKUP_PROVEN"
    assert result["production_touched"] is False
    assert result["secrets_read"] is False


def test_canary_rejects_runner_name_mismatch(tmp_path: Path) -> None:
    with patch.dict(
        subject.os.environ,
        {
            "RUNNER_NAME": "OTHER-RUNNER",
            "GITHUB_REPOSITORY": "ericson-j-santos/reqsys-v2-enterprise-real",
            "GITHUB_SHA": "a" * 40,
        },
        clear=False,
    ):
        with pytest.raises(subject.CanaryError, match="runner_name_mismatch"):
            subject.execute(
                confirm=subject.CONFIRM,
                evidence_file=tmp_path / "evidence.json",
                host=subject.TARGET_HOST,
                platform="nt",
            )


def test_canary_failure_evidence_does_not_leak_exception(tmp_path: Path) -> None:
    evidence = tmp_path / "blocked.json"
    with (
        patch.object(
            subject,
            "execute",
            side_effect=subject.CanaryError("token=must-not-leak"),
        ),
        patch(
            "sys.argv",
            [
                "desktop_runner_pickup_canary.py",
                "--confirm",
                subject.CONFIRM,
                "--evidence-file",
                str(evidence),
            ],
        ),
    ):
        assert subject.main() == 2

    persisted = evidence.read_text(encoding="utf-8")
    assert "must-not-leak" not in persisted
    payload = subject.json.loads(persisted)
    assert payload["error"] == "desktop_runner_pickup_not_proven"
