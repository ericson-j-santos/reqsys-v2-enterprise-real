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
    LedgerError,
    LinkedInPublishError,
    build_linkedin_headers,
    build_linkedin_payload,
    execute_dry_run,
    execute_publish,
    ledger_comment,
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


class FakeHttpResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status = status
        self.headers = headers or {}
        self._payload = payload

    def getcode(self):
        return self.status

    def read(self):
        if self._payload is None:
            return b""
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeLinkedInOpener:
    def __init__(self):
        self.calls = []

    def __call__(self, request, timeout=30):
        self.calls.append((request, timeout))
        return FakeHttpResponse(
            201,
            headers={"x-restli-id": "urn:li:share:123"},
        )


class FakeGitHubOpener:
    def __init__(self, comments=None):
        self.calls = []
        self.comments = list(comments or [])
        self.next_id = 1000

    def __call__(self, request, timeout=30):
        self.calls.append((request.get_method(), request.full_url))
        method = request.get_method()
        url = request.full_url

        if method == "GET" and "/comments?" in url:
            return FakeHttpResponse(200, payload=self.comments)

        if method == "POST" and url.endswith("/comments"):
            body = json.loads(request.data.decode("utf-8"))["body"]
            self.next_id += 1
            item = {"id": self.next_id, "body": body}
            self.comments.append(item)
            return FakeHttpResponse(201, payload=item)

        if method == "PATCH" and "/issues/comments/" in url:
            comment_id = int(url.rsplit("/", 1)[-1])
            body = json.loads(request.data.decode("utf-8"))["body"]
            for item in self.comments:
                if int(item["id"]) == comment_id:
                    item["body"] = body
                    return FakeHttpResponse(200, payload=item)
            return FakeHttpResponse(404, payload={"message": "not found"})

        raise AssertionError(f"GitHub fake não cobre {method} {url}")


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
                execute_dry_run(
                    report=report(),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-1",
                    confirmation="YES",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    api_version="202609",
                    ledger_path=Path(tmp) / "ledger.json",
                )

    def test_approval_rejects_candidate_not_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ApprovalError):
                execute_dry_run(
                    report=report(selected=False),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-2",
                    confirmation="APPROVE",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    api_version="202609",
                    ledger_path=Path(tmp) / "ledger.json",
                )

    def test_dry_run_is_network_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = execute_dry_run(
                report=report(),
                content_hash=CONTENT_HASH,
                approved_by="ci-e2e",
                correlation_id="corr-dry",
                confirmation="APPROVE",
                approval_kind="test",
                author_urn="urn:li:person:ci-e2e",
                api_version="202609",
                ledger_path=Path(tmp) / "ledger.json",
            )
        self.assertEqual("DRY_RUN_APPROVED", result["status"])
        self.assertFalse(result["published"])
        self.assertEqual(LINKEDIN_POSTS_URL, result["linkedin"]["endpoint"])
        self.assertEqual("local_dry_run", result["idempotency"]["backend"])

    def test_publish_requires_human_approval(self):
        with self.assertRaises(ApprovalError):
            execute_publish(
                report=report(),
                content_hash=CONTENT_HASH,
                approved_by="ci",
                correlation_id="corr-test",
                confirmation="APPROVE",
                approval_kind="test",
                author_urn="urn:li:person:123",
                api_version="202609",
                ledger_repository="example/repo",
                ledger_issue=1862,
                github_token="github-test",
                linkedin_token="linkedin-test",
            )

    def test_publish_is_feature_flagged_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LinkedInPublishError):
                execute_publish(
                    report=report(),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-flag",
                    confirmation="APPROVE",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    api_version="202609",
                    ledger_repository="example/repo",
                    ledger_issue=1862,
                    github_token="github-test",
                    linkedin_token="linkedin-test",
                )

    def test_persistent_ledger_prevents_duplicate_linkedin_call(self):
        github = FakeGitHubOpener()
        linkedin = FakeLinkedInOpener()
        with patch.dict(os.environ, {"REQSYS_LINKEDIN_PUBLISH_ENABLED": "true"}, clear=True):
            first = execute_publish(
                report=report(),
                content_hash=CONTENT_HASH,
                approved_by="reviewer",
                correlation_id="corr-publish-1",
                confirmation="APPROVE",
                approval_kind="human",
                author_urn="urn:li:person:123",
                api_version="202609",
                ledger_repository="example/repo",
                ledger_issue=1862,
                github_token="github-test",
                linkedin_token="linkedin-test",
                linkedin_opener=linkedin,
                github_opener=github,
            )
            second = execute_publish(
                report=report(),
                content_hash=CONTENT_HASH,
                approved_by="reviewer",
                correlation_id="corr-publish-2",
                confirmation="APPROVE",
                approval_kind="human",
                author_urn="urn:li:person:123",
                api_version="202609",
                ledger_repository="example/repo",
                ledger_issue=1862,
                github_token="github-test",
                linkedin_token="linkedin-test",
                linkedin_opener=linkedin,
                github_opener=github,
            )

        self.assertEqual("PUBLISHED", first["status"])
        self.assertEqual("urn:li:share:123", first["post_id"])
        self.assertEqual("ALREADY_PUBLISHED", second["status"])
        self.assertEqual(1, len(linkedin.calls))
        self.assertIn('"state":"PUBLISHED"', github.comments[-1]["body"])

    def test_prepared_ledger_blocks_automatic_retry(self):
        prepared = {
            "schema_version": 1,
            "state": "PREPARED",
            "content_hash": CONTENT_HASH,
            "correlation_id": "old-corr",
            "approved_by": "reviewer",
            "pr_number": 1900,
            "source_head_sha": "b" * 40,
            "post_id": None,
            "updated_at": "2026-09-20T00:00:00Z",
        }
        github = FakeGitHubOpener(comments=[{"id": 77, "body": ledger_comment(prepared)}])
        linkedin = FakeLinkedInOpener()
        with patch.dict(os.environ, {"REQSYS_LINKEDIN_PUBLISH_ENABLED": "true"}, clear=True):
            with self.assertRaises(LedgerError):
                execute_publish(
                    report=report(),
                    content_hash=CONTENT_HASH,
                    approved_by="reviewer",
                    correlation_id="corr-retry",
                    confirmation="APPROVE",
                    approval_kind="human",
                    author_urn="urn:li:person:123",
                    api_version="202609",
                    ledger_repository="example/repo",
                    ledger_issue=1862,
                    github_token="github-test",
                    linkedin_token="linkedin-test",
                    linkedin_opener=linkedin,
                    github_opener=github,
                )
        self.assertEqual([], linkedin.calls)


if __name__ == "__main__":
    unittest.main()
