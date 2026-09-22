from datetime import datetime, timezone

import pytest

from app.domain.change_evidence import (
    ChangeExecutionEvidence,
    ChangeValidationStatus,
    assert_change_can_close,
)
from app.domain.service_management import ServiceManagementValidationError


def _digest(value: str = "a") -> str:
    return value * 64


def _evidence(
    *,
    status: ChangeValidationStatus = ChangeValidationStatus.PASSED,
    runtime_sha: str | None = None,
    **kwargs,
) -> ChangeExecutionEvidence:
    head_sha = "a" * 40
    payload = {
        "head_sha": head_sha,
        "deployment_ref": "github-actions:run-1789",
        "environment": "dev",
        "runtime_sha": runtime_sha or head_sha,
        "post_deploy_evidence_uri": "urn:reqsys:rsm-07:post-deploy",
        "post_deploy_evidence_sha256": _digest("b"),
        "status": status,
        "observed_at": datetime.now(timezone.utc),
    }
    payload.update(kwargs)
    return ChangeExecutionEvidence(**payload)


def test_passed_evidence_allows_change_close():
    evidence = _evidence()

    assert evidence.allows_close is True
    assert_change_can_close(evidence)


def test_runtime_sha_must_equal_change_head_sha():
    with pytest.raises(ServiceManagementValidationError, match="runtime SHA divergente"):
        _evidence(runtime_sha="c" * 40)


def test_failed_post_deploy_blocks_close_until_rollback_is_proven():
    failed = _evidence(status=ChangeValidationStatus.FAILED)

    assert failed.allows_close is False
    with pytest.raises(ServiceManagementValidationError, match="rollback não foi comprovado"):
        assert_change_can_close(failed)


def test_rolled_back_evidence_requires_complete_and_distinct_runtime():
    with pytest.raises(ServiceManagementValidationError, match="rollback exige"):
        _evidence(
            status=ChangeValidationStatus.ROLLED_BACK,
            rollback_ref="revert:123",
        )

    with pytest.raises(ServiceManagementValidationError, match="deve divergir"):
        _evidence(
            status=ChangeValidationStatus.ROLLED_BACK,
            rollback_ref="revert:123",
            rollback_runtime_sha="a" * 40,
            rollback_evidence_uri="urn:reqsys:rsm-07:rollback",
            rollback_evidence_sha256=_digest("c"),
        )

    rolled_back = _evidence(
        status=ChangeValidationStatus.ROLLED_BACK,
        rollback_ref="revert:123",
        rollback_runtime_sha="d" * 40,
        rollback_evidence_uri="urn:reqsys:rsm-07:rollback",
        rollback_evidence_sha256=_digest("c"),
    )
    assert rolled_back.allows_close is True
    assert_change_can_close(rolled_back)


def test_missing_runtime_evidence_blocks_close():
    with pytest.raises(ServiceManagementValidationError, match="sem evidência runtime"):
        assert_change_can_close(None)
