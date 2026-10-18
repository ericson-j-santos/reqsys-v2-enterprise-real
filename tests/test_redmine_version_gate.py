from __future__ import annotations

import pytest

from scripts.redmine_version_gate import (
    RedmineVersionError,
    evaluate_redmine_version,
    format_version,
    parse_redmine_version,
)


@pytest.mark.parametrize(
    "version",
    [
        "6.1.5", "6.1.9", "7.0.2", "7.0.12",
        "6.1.5.stable", "7.0.2.stable.23000", " 6.1.5 ",
    ],
)
def test_accepts_homologated_versions_at_or_above_security_floor(version: str) -> None:
    decision = evaluate_redmine_version(version)
    assert decision.allowed is True
    assert decision.reason == "redmine_version_suportada"


@pytest.mark.parametrize(
    ("version", "minimum"),
    [
        ("6.1.0", (6, 1, 5)), ("6.1.3", (6, 1, 5)),
        ("6.1.4", (6, 1, 5)), ("6.1.4.stable", (6, 1, 5)),
        ("7.0.0", (7, 0, 2)), ("7.0.1", (7, 0, 2)),
        ("7.0.1.stable", (7, 0, 2)),
    ],
)
def test_blocks_versions_below_security_floor(
    version: str,
    minimum: tuple[int, int, int],
) -> None:
    decision = evaluate_redmine_version(version)
    assert decision.allowed is False
    assert decision.reason == "redmine_version_vulneravel"
    assert decision.minimum == minimum


@pytest.mark.parametrize("version", ["6.0.0", "6.0.10", "6.0.11", "6.0.99"])
def test_blocks_series_without_reviewed_security_fix_not_as_eol(version: str) -> None:
    decision = evaluate_redmine_version(version)
    assert decision.allowed is False
    assert decision.reason == "redmine_version_sem_correcao_homologada"
    assert decision.minimum is None


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


@pytest.mark.parametrize(
    "version",
    [
        "", "7", "7.0", "release-7.0.2", "abc", None, 615,
        "6.1.5.devel", "7.0.2-rc1", "6.1.5+unreviewed",
        "7.0.2.stable.evil", "6.1.5 arbitrary", "6.1.5\nignored",
        "６.１.５",
    ],
)
def test_rejects_unparseable_or_unreviewed_version(version: object) -> None:
    with pytest.raises(RedmineVersionError):
        parse_redmine_version(version)


@pytest.mark.parametrize("version", ["6.0.11", "6.1.4", "7.0.1"])
def test_negative_control_pre_october_security_floor_never_passes(version: str) -> None:
    assert evaluate_redmine_version(version).allowed is False


@pytest.mark.parametrize("version", ["6.1.5", "6.1.4", "6.0.11", "7.0.2", "7.1.0"])
def test_repeated_evaluation_is_idempotent(version: str) -> None:
    first = evaluate_redmine_version(version)
    for _ in range(10):
        assert evaluate_redmine_version(version) == first


def test_format_version_contract_is_preserved() -> None:
    assert format_version(parse_redmine_version("7.0.2.stable.23000")) == "7.0.2"
