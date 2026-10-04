from __future__ import annotations

import pytest

from scripts.redmine_version_gate import (
    RedmineVersionError,
    evaluate_redmine_version,
    parse_redmine_version,
)


@pytest.mark.parametrize(
    "version",
    ["6.0.11", "6.0.99", "6.1.4", "6.1.9", "7.0.1", "7.0.2", "7.0.1.stable"],
)
def test_accepts_homologated_versions_at_or_above_security_floor(version: str) -> None:
    decision = evaluate_redmine_version(version)
    assert decision.allowed is True
    assert decision.reason == "redmine_version_suportada"


@pytest.mark.parametrize(
    ("version", "minimum"),
    [("6.0.10", (6, 0, 11)), ("6.1.3", (6, 1, 4)), ("7.0.0", (7, 0, 1))],
)
def test_blocks_versions_below_security_floor(
    version: str,
    minimum: tuple[int, int, int],
) -> None:
    decision = evaluate_redmine_version(version)
    assert decision.allowed is False
    assert decision.reason == "redmine_version_vulneravel"
    assert decision.minimum == minimum


@pytest.mark.parametrize("version", ["5.1.9", "5.0.12", "4.2.11"])
def test_blocks_eol_major_versions(version: str) -> None:
    decision = evaluate_redmine_version(version)
    assert decision.allowed is False
    assert decision.reason == "redmine_version_eol"


@pytest.mark.parametrize("version", ["6.2.0", "7.1.0", "8.0.0"])
def test_blocks_future_or_unhomologated_series(version: str) -> None:
    decision = evaluate_redmine_version(version)
    assert decision.allowed is False
    assert decision.reason == "redmine_version_nao_homologada"


@pytest.mark.parametrize("version", ["", "7", "7.0", "release-7.0.1", "abc"])
def test_rejects_unparseable_version(version: str) -> None:
    with pytest.raises(RedmineVersionError):
        parse_redmine_version(version)


def test_negative_control_known_vulnerable_release_never_passes() -> None:
    assert evaluate_redmine_version("7.0.0").allowed is False
