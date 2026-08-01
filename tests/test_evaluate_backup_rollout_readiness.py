from scripts.evaluate_backup_rollout_readiness import evaluate

def valid_evidence() -> dict:
    digest = "a" * 64
    counts = "b" * 64
    return {
        "control_id": "BACEN-04",
        "environment": "dev",
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
        "correlation_id": "backup-1-dev",
        "run_url": "https://github.com/example/repo/actions/runs/1",
    }

def test_valid_dev_evidence_allows_only_stg_candidate() -> None:
    report = evaluate(valid_evidence(), source_run_id="1", source_artifact_digest="sha256:x")
    assert report["decision"] == "stg_rollout_candidate"
    assert report["stg_allowed"] is True
    assert report["prod_allowed"] is False
    assert report["automatic_prod_enable_allowed"] is False
    assert report["production_touched"] is False

def test_missing_evidence_is_blocked() -> None:
    report = evaluate(None, source_run_id="2", source_artifact_digest="")
    assert report["decision"] == "blocked_missing_dev_evidence"
    assert report["stg_allowed"] is False

def test_hash_mismatch_blocks_rollout() -> None:
    evidence = valid_evidence()
    evidence["restored_manifest"]["sha256"] = "c" * 64
    report = evaluate(evidence, source_run_id="3", source_artifact_digest="")
    assert report["stg_allowed"] is False
    assert any(item["name"] == "sha256_equal" and not item["passed"] for item in report["checks"])

def test_quota_warning_blocks_stg_expansion() -> None:
    evidence = valid_evidence()
    evidence["quota"]["status"] = "warning"
    report = evaluate(evidence, source_run_id="4", source_artifact_digest="")
    assert report["stg_allowed"] is False
    assert report["decision"] == "blocked_invalid_dev_evidence"

def test_rto_violation_blocks_rollout() -> None:
    evidence = valid_evidence()
    evidence["rto_seconds"] = 30000
    report = evaluate(evidence, source_run_id="5", source_artifact_digest="")
    assert report["stg_allowed"] is False

def test_prod_evidence_never_enables_stg_or_prod() -> None:
    evidence = valid_evidence()
    evidence["environment"] = "prod"
    evidence["production_read_only"] = True
    report = evaluate(evidence, source_run_id="6", source_artifact_digest="")
    assert report["stg_allowed"] is False
    assert report["prod_allowed"] is False
