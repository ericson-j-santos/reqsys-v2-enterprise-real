import unittest

from scripts.reqsys_product_story_engine import build_candidate, build_report, render_markdown


def item(**overrides):
    base = {
        "number": 1850,
        "title": "Worker Pool governado com validação independente",
        "url": "https://github.com/example/repo/pull/1850",
        "merged_at": "2026-09-20T12:00:00Z",
        "head_sha": "a" * 40,
        "files": ["backend/app.py", "docs/worker-pool.md", ".sdd/specs/worker-pool.spec.json"],
        "checks": [{"name": "CI", "status": "completed", "conclusion": "success", "url": "https://example/check"}],
        "implemented": True,
        "validated": True,
        "evidenced": True,
        "consolidated": True,
        "governed": True,
        "evidence_gaps": [],
    }
    base.update(overrides)
    return base


class ReqSysProductStoryEngineTests(unittest.TestCase):
    def test_grounded_delivery_becomes_review_only_draft(self):
        candidate = build_candidate(item())
        self.assertEqual("READY_FOR_HUMAN_REVIEW", candidate["status"])
        self.assertTrue(candidate["approval"]["required"])
        self.assertFalse(candidate["approval"]["approved"])
        self.assertFalse(candidate["approval"]["published"])
        self.assertIn("PR #1850", candidate["linkedin"]["post_text"])
        self.assertIn("aaaaaaaaaaaa", candidate["linkedin"]["post_text"])

    def test_missing_evidence_blocks_candidate(self):
        candidate = build_candidate(item(evidenced=False, evidence_gaps=["check_url_ausente"]))
        self.assertEqual("BLOCKED", candidate["status"])
        self.assertIn("evidenced_required", candidate["blockers"])
        self.assertIn("evidence_gaps_present", candidate["blockers"])

    def test_sensitive_signal_blocks_candidate(self):
        candidate = build_candidate(item(title="Rotação de secret e token operacional"))
        self.assertEqual("BLOCKED", candidate["status"])
        self.assertTrue(any(blocker.startswith("sensitive_signal:") for blocker in candidate["blockers"]))

    def test_content_hash_is_idempotent_for_same_source(self):
        first = build_candidate(item())
        second = build_candidate(item())
        self.assertEqual(first["linkedin"]["content_hash"], second["linkedin"]["content_hash"])

    def test_report_selects_top_ready_candidates_only(self):
        lower = item(number=1849, governed=False, title="Entrega consolidada A", head_sha="b" * 40)
        higher = item(number=1851, governed=True, title="Entrega consolidada B", head_sha="c" * 40)
        blocked = item(number=1852, validated=False, title="Entrega sem validação", head_sha="d" * 40)
        report = build_report({"repository": "example/repo", "items": [lower, higher, blocked]}, limit=1)
        selected = [c for c in report["candidates"] if c["selected_for_review"]]
        self.assertEqual(1, len(selected))
        self.assertEqual(1851, selected[0]["pr_number"])
        self.assertEqual(1, report["summary"]["blocked"])

    def test_markdown_states_human_review_and_no_auto_publish(self):
        report = build_report({"repository": "example/repo", "items": [item()]}, limit=1)
        text = render_markdown(report)
        self.assertIn("Nenhum conteúdo é publicado automaticamente", text)
        self.assertIn("Hash idempotente", text)


if __name__ == "__main__":
    unittest.main()
