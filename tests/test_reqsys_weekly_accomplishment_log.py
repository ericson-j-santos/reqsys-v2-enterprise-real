import unittest

from scripts.reqsys_weekly_accomplishment_log import classify_item, compare_summary, coverage, render_markdown


def pr(*, checks=None, files=None):
    return {
        "number": 123,
        "title": "Incremento verificável",
        "html_url": "https://github.com/example/repo/pull/123",
        "merged_at": "2026-09-18T12:00:00Z",
        "head_sha": "a" * 40,
        "files": files if files is not None else ["backend/app.py"],
        "checks": checks if checks is not None else [
            {
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/example/repo/actions/runs/1",
            }
        ],
    }


class ReqSysWeeklyAccomplishmentLogTests(unittest.TestCase):
    def test_classifies_all_dimensions_from_grounded_evidence(self):
        item = classify_item(pr(files=["backend/app.py", ".sdd/specs/x.spec.json", "docs/x.md"]))
        self.assertTrue(item["implemented"])
        self.assertTrue(item["validated"])
        self.assertTrue(item["evidenced"])
        self.assertTrue(item["consolidated"])
        self.assertTrue(item["governed"])
        self.assertEqual([], item["evidence_gaps"])

    def test_failed_check_blocks_validation_and_governance(self):
        checks = [
            {"name": "CI", "status": "completed", "conclusion": "failure", "html_url": "https://example/check"}
        ]
        item = classify_item(pr(checks=checks, files=[".github/workflows/ci.yml"]))
        self.assertTrue(item["implemented"])
        self.assertFalse(item["validated"])
        self.assertFalse(item["governed"])
        self.assertIn("checks_sem_sucesso_confirmado", item["evidence_gaps"])

    def test_missing_checks_blocks_evidence(self):
        item = classify_item(pr(checks=[]))
        self.assertFalse(item["validated"])
        self.assertFalse(item["evidenced"])
        self.assertIn("check_url_ausente", item["evidence_gaps"])

    def test_coverage_is_evidence_coverage_not_project_progress(self):
        items = [classify_item(pr()), classify_item(pr(checks=[]))]
        result = coverage(items)
        self.assertEqual(100.0, result["implemented"])
        self.assertEqual(50.0, result["validated"])
        self.assertEqual(50.0, result["evidenced"])

    def test_compare_summary_uses_previous_counts(self):
        current = {"counts": {"implemented": 4, "validated": 3}}
        previous = {"counts": {"implemented": 2, "validated": 3}}
        delta = compare_summary(current, previous)
        self.assertEqual(2, delta["implemented"])
        self.assertEqual(0, delta["validated"])

    def test_markdown_flags_missing_baseline_and_global_progress_warning(self):
        report = {
            "repository": "example/repo",
            "window": {"start": "2026-09-11", "end": "2026-09-18"},
            "generated_at": "2026-09-18T12:00:00Z",
            "counts": {"implemented": 1, "validated": 0, "evidenced": 0, "consolidated": 0, "governed": 0},
            "coverage_percent": {"implemented": 100.0, "validated": 0.0, "evidenced": 0.0, "consolidated": 0.0, "governed": 0.0},
            "delta_from_previous": None,
            "items": [classify_item(pr(checks=[]))],
        }
        text = render_markdown(report)
        self.assertIn("não representa percentual global", text.lower())
        self.assertIn("baseline anterior não encontrado", text.lower())
        self.assertIn("checks_sem_sucesso_confirmado", text)


if __name__ == "__main__":
    unittest.main()
