from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "kindle_knowledge_local_cache.py"
WORKFLOW = ROOT / ".github" / "workflows" / "kindle-knowledge-local-cache.yml"
POLICY = ROOT / ".github" / "self-hosted-runner-policy.json"

SPEC = importlib.util.spec_from_file_location("kindle_knowledge_local_cache", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_query_bundle_has_seven_statements() -> None:
    sql = mod.render_sql()
    assert len(mod.QUERIES) == 7
    assert sql.count(";") == 7
    assert mod.validate_queries(sql) == []


def test_negative_query_validation_detects_missing_token() -> None:
    sql = mod.render_sql().replace("stddev_pop", "stddev_removed", 1)
    errors = mod.validate_queries(sql)
    assert any("stddev_pop" in error for error in errors)


def test_output_root_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(mod.MaterializeError, match="output_root não autorizado"):
        mod.validate_output_root(tmp_path)


def test_host_guard_rejects_unapproved_expected_host() -> None:
    with pytest.raises(mod.MaterializeError, match="não autorizado"):
        mod.validate_host("OTHER-HOST")


def test_workflow_uses_both_self_hosted_hosts_and_schedule() -> None:
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "schedule:" in raw
    assert "cron: '15 11 * * *'" in raw
    assert "runs-on: [self-hosted, Windows, X64, noteri, reqsys-dev]" in raw
    assert "runs-on: [self-hosted, Windows, X64, pc24x7, reqsys-dev]" in raw
    assert "MATERIALIZE-KINDLE-QUERIES" in raw
    assert "C:\\dev\\chatgpt-workers\\kindle-knowledge-local" in raw
    assert "secrets." not in raw


def test_workflow_is_allowlisted() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert ".github/workflows/kindle-knowledge-local-cache.yml" in policy["approved_workflows"]


def test_script_never_reads_credentials() -> None:
    raw = SCRIPT.read_text(encoding="utf-8").casefold()
    assert ".env" not in raw
    assert "credential" not in raw
    assert "token.json" not in raw
    assert "refresh_token" not in raw
