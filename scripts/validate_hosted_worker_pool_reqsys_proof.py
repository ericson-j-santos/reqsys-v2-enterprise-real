#!/usr/bin/env python3
"""Validate the bounded public receipt of the hosted ReqSys Worker Pool proof."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SHA40 = re.compile(r"^[0-9a-f]{40}$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--reqsys-sha", required=True)
    parser.add_argument("--worker-pool-sha", required=True)
    parser.add_argument("--rules-sha", required=True)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        assert args.input.stat().st_size <= 65536
        assert all(SHA40.fullmatch(value) for value in (
            args.reqsys_sha, args.worker_pool_sha, args.rules_sha
        ))
        assert payload["result"] == "REQSYS_HOSTED_WORKER_POOL_PROOF_PASSED"
        assert payload["environment"] == "DEV"
        assert payload["reqsys_sha"] == args.reqsys_sha
        assert payload["worker_pool_sha"] == args.worker_pool_sha
        assert payload["rules_sha"] == args.rules_sha
        assert payload["issue_number"] == args.issue_number
        assert payload["request_id"] == args.request_id
        assert payload["real_reqsys_task_executed"] is True
        assert payload["simulated"] is False
        assert payload["fencing_required"] is True
        assert payload["legacy_exact_claim_rejected"] is True
        assert payload["replay_created"] is False
        assert payload["negative_auth_status"] == 401
        assert payload["independent_validator_process"] is True
        assert payload["independent_postgres_readback"] is True
        assert payload["storage_backend"] == "postgres"
        assert payload["production_touched"] is False
        assert payload["deploy_executed"] is False
        assert payload["merge_executed"] is False
        assert payload["additional_cost_brl"] == "0.00"
        assert isinstance(payload["task_id"], str) and payload["task_id"].startswith("cwp-")
        assert isinstance(payload["work_id"], str) and payload["work_id"].startswith("work-")
    except (AssertionError, KeyError, OSError, ValueError, TypeError, json.JSONDecodeError):
        print("REQSYS_HOSTED_WORKER_POOL_PROOF_INVALID")
        return 2
    print("REQSYS_HOSTED_WORKER_POOL_PROOF_VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
