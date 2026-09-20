import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.reqsys_product_story_linkedin import (
    ApprovalError,
    DEFAULT_LINKEDIN_VERSION,
    LINKEDIN_POSTS_URL,
    LinkedInPublishError,
    build_linkedin_headers,
    build_linkedin_payload,
    execute,
)


CONTENT_HASH = "a" * 64


def report(*, selected=True, status="READY_FOR_HUMAN_REVIEW"):
    return {
        "candidates": [
            {
                "pr_number": 1900,
                "title": "Entrega validada",
                "status": status,
                "selected_for_review": selected,
                "source": {"head_sha": "b" * 40},
                "linkedin": {
                    "content_hash": CONTENT_HASH,
                    "post_text": "ReqSys: entrega validada\n\n#ReqSys",
                },
            }
        ]
    }


class FakeResponse:
    status = 201

    def __init__(self, post_id="urn:li:share:123"):
        self.headers = {"x-restli-id": post_id}

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self):
        self.calls = []

    def __call__(self, request, timeout=30):
        self.calls.append((request, timeout))
        return FakeResponse()


class ReqSysProductStoryLinkedInTests(unittest.TestCase):
    def test_builds_official_posts_api_contract(self):
        candidate = report()["candidates"][0]
        payload = build_linkedin_payload(candidate, "urn:li:person:123")
        self.assertEqual("urn:li:person:123", payload["author"])
        self.assertEqual("PUBLIC", payload["visibility"])
        self.assertEqual("MAIN_FEED", payload["distribution"]["feedDistribution"])
        self.assertEqual("PUBLISHED", payload["lifecycleState"])

        headers = build_linkedin_headers(token="secret-value", api_version=DEFAULT_LINKEDIN_VERSION)
        self.assertEqual("2.0.0", headers["X-Restli-Protocol-Version"])
        self.assertEqual("202609", headers["Linkedin-Version"])
        self.assertTrue(headers["Authorization"].startswith("Bearer "))

    def test_approval_rejects_wrong_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ApprovalError):
                execute(
                    report=report(),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-1",
                    confirmation="YES",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    mode="dry_run",
                    api_version="202609",
                    ledger_path=Path(tmp) / "ledger.json",
                )

    def test_approval_rejects_candidate_not_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ApprovalError):
                execute(
                    report=report(selected=False),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-2",
                    confirmation="APPROVE",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    mode="dry_run",
                    api_version="202609",
                    ledger_path=Path(tmp) / "ledger.json",
                )

    def test_dry_run_never_calls_network(self):
        opener = FakeOpener()
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(
                report=report(),
                content_hash=CONTENT_HASH,
                approved_by="ci-e2e",
                correlation_id="corr-dry",
                confirmation="APPROVE",
                approval_kind="test",
                author_urn="urn:li:person:ci-e2e",
                mode="dry_run",
                api_version="202609",
                ledger_path=Path(tmp) / "ledger.json",
                opener=opener,
            )
        self.assertEqual("DRY_RUN_APPROVED", result["status"])
        self.assertFalse(result["published"])
        self.assertEqual([], opener.calls)
        self.assertEqual(LINKEDIN_POSTS_URL, result["linkedin"]["endpoint"])

    def test_publish_requires_human_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ApprovalError):
                execute(
                    report=report(),
                    content_hash=CONTENT_HASH,
                    approved_by="ci",
                    correlation_id="corr-test",
                    confirmation="APPROVE",
                    approval_kind="test",
                    author_urn="urn:li:person:123",
                    mode="publish",
                    api_version="202609",
                    ledger_path=Path(tmp) / "ledger.json",
                )

    def test_publish_is_feature_flagged_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(LinkedInPublishError):
                    execute(
                        report=report(),
                        content_hash=CONTENT_HASH,
                        approved_by="reviewer",
                        correlation_id="corr-flag",
                        confirmation="APPROVE",
                        approval_kind="human",
                        author_urn="urn:li:person:123",
                        mode="publish",
                        api_version="202609",
                        ledger_path=Path(tmp) / "ledger.json",
                    )

    def test_publish_records_post_and_blocks_duplicate_network_call(self):
        opener = FakeOpener()
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "ledger.json"
            env = {
                "REQSYS_LINKEDIN_PUBLISH_ENABLED": "true",
                "LINKEDIN_ACCESS_TOKEN": "token-for-test-only",
            }
            with patch.dict(os.environ, env, clear=True):
                first = execute(
                    report=report(),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-publish-1",
                    confirmation="APPROVE",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    mode="publish",
                    api_version="202609",
                    ledger_path=ledger,
                    opener=opener,
                )
                second = execute(
                    report=report(),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-publish-2",
                    confirmation="APPROVE",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    mode="publish",
                    api_version="202609",
                    ledger_path=ledger,
                    opener=opener,
                )

            saved = json.loads(ledger.read_text(encoding="utf-8"))

        self.assertEqual("PUBLISHED", first["status"])
        self.assertEqual("urn:li:share:123", first["post_id"])
        self.assertEqual("ALREADY_PUBLISHED", second["status"])
        self.assertEqual(1, len(opener.calls))
        self.assertIn(CONTENT_HASH, saved["publications"])


if __name__ == "__main__":
    unittest.main()
