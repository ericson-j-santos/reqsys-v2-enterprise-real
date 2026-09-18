from scripts.evaluate_backup_rollout_readiness import evaluate


def valid_digest() -> str:
    return "sha256:" + ("d" * 64)


def valid_evidence(environment: str = "dev") -> dict:
    digest = "a" * 64
    counts = "b" * 64
    return {
        "control_id": "BACEN-04",
        "environment": environment,
        "result": "passed",
        "integrity_match": True,
        "source_manifest": {
            "quick_check": "ok",
            "sha256": digest,
            "table_counts_sha256": counts,
        },
        "restored_manifest": {
            "quick_check": "ok",
            "sha256": digest,
            "table_counts_sha256": counts,
        },
        "rpo_minutes": 10.0,
        "rpo_target_minutes": 1440,
        "rto_seconds": 120.0,
        "rto_target_seconds": 28800,
        "quota": {"status": "healthy"},
        "production_read_only": False,
        "production_restore_claimed": False,
        "snapshot_id": "snapshot-1",
        "correlation_id": f"backup-1-{environment}",
        "run_url": "https://github.com/example/repo/actions/runs/1",
    }


def test_valid_dev_evidence_allows_only_stg_candidate() -> None:
    report = evaluate(
        valid_evidence(),
        source_run_id="1",
        source_artifact_digest=valid_digest(),
        source_environment="dev",
    )
    assert report["decision"] == "stg_rollout_candidate"
    assert report["stg_allowed"] is True
    assert report["prod_allowed"] is False
    assert report["automatic_prod_enable_allowed"] is False
    assert report["human_prod_approval_required"] is False
    assert report["production_touched"] is False


def test_valid_stg_evidence_allows_prod_candidate_but_requires_human_approval() -> None:
    report = evaluate(
        valid_evidence("stg"),
        source_run_id="2",
        source_artifact_digest=valid_digest(),
        source_environment="stg",
    )
    assert report["decision"] == "prod_rollout_candidate_requires_approval"
    assert report["stg_allowed"] is False
    assert report["prod_allowed"] is True
    assert report["human_prod_approval_required"] is True
    assert report["automatic_prod_enable_allowed"] is False
    assert report["production_touched"] is False


def test_missing_evidence_is_blocked() -> None:
    report = evaluate(
        None,
        source_run_id="3",
        source_artifact_digest=valid_digest(),
        source_environment="stg",
    )
    assert report["decision"] == "blocked_missing_stg_evidence"
    assert report["prod_allowed"] is False


def test_invalid_artifact_digest_blocks_rollout() -> None:
    report = evaluate(
        valid_evidence(),
        source_run_id="4",
        source_artifact_digest="sha256:invalid",
        source_environment="dev",
    )
    assert report["stg_allowed"] is False
    assert any(
        item["name"] == "artifact_digest_sha256_valid" and not item["passed"]
        for item in report["checks"]
    )


def test_hash_mismatch_blocks_rollout() -> None:
    evidence = valid_evidence()
    evidence["restored_manifest"]["sha256"] = "c" * 64
    report = evaluate(
        evidence,
        source_run_id="5",
        source_artifact_digest=valid_digest(),
        source_environment="dev",
    )
    assert report["stg_allowed"] is False
    assert any(item["name"] == "sha256_equal" and not item["passed"] for item in report["checks"])


def test_quota_warning_blocks_stg_expansion() -> None:
    evidence = valid_evidence()
    evidence["quota"]["status"] = "warning"
    report = evaluate(
        evidence,
        source_run_id="6",
        source_artifact_digest=valid_digest(),
        source_environment="dev",
    )
    assert report["stg_allowed"] is False
    assert report["decision"] == "blocked_invalid_dev_evidence"


def test_rto_violation_blocks_prod_candidate() -> None:
    evidence = valid_evidence("stg")
    evidence["rto_seconds"] = 30000
    report = evaluate(
        evidence,
        source_run_id="7",
        source_artifact_digest=valid_digest(),
        source_environment="stg",
    )
    assert report["prod_allowed"] is False
    assert report["decision"] == "blocked_invalid_stg_evidence"


def test_prod_evidence_never_enables_stg_or_prod_when_dev_is_expected() -> None:
    evidence = valid_evidence("prod")
    evidence["production_read_only"] = True
    report = evaluate(
        evidence,
        source_run_id="8",
        source_artifact_digest=valid_digest(),
        source_environment="dev",
    )
    assert report["stg_allowed"] is False
    assert report["prod_allowed"] is False
