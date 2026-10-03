from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime"))

from scripts.e2e_platform_central_pilot import (  # noqa: E402
    REQUIRED_MARKERS,
    build_evidence,
    require_markers,
    validate_identity,
)


class E2EPlatformCentralPilotTests(unittest.TestCase):
    def test_required_markers_accept_complete_real_e2e_output(self) -> None:
        require_markers("\n".join(REQUIRED_MARKERS))

    def test_required_markers_fail_closed_when_control_is_missing(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "e2e_required_markers_missing"):
            require_markers("\n".join(REQUIRED_MARKERS[:-1]))

    def test_evidence_is_bound_to_same_sha_and_correlation_id(self) -> None:
        now = datetime(2026, 9, 23, 16, 0, tzinfo=UTC)
        evidence = build_evidence(
            repository="ericson-j-santos/reqsys-v2-enterprise-real",
            sha="a" * 40,
            environment="ci",
            correlation_id="reqsys-central-12345678",
            started_at=now,
            completed_at=now,
        )
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["sha"], "a" * 40)
        self.assertEqual(evidence["correlation_id"], "reqsys-central-12345678")
        self.assertIs(evidence["negative_control"]["passed"], True)
        self.assertIs(evidence["independent_read"]["passed"], True)
        self.assertIs(evidence["idempotency"]["passed"], True)

    def test_identity_requires_full_sha(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "sha_must_be_full_40_chars"):
            validate_identity("ericson-j-santos/reqsys-v2-enterprise-real", "abc123")


if __name__ == "__main__":
    unittest.main()
