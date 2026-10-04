import tempfile
import unittest
from pathlib import Path

from scripts.validate_repository_domain_routing import validate_inventory


class RepositoryDomainRoutingTests(unittest.TestCase):
    def _root(self, workflow_names: list[str]) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        workflow_dir = root / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)
        for name in workflow_names:
            (workflow_dir / name).write_text("name: test\n", encoding="utf-8")
        return root

    def _payload(self, workflow_names: list[str]) -> dict:
        bacen = sorted(name for name in workflow_names if name.startswith("bacen-"))
        return {
            "source_repository": "ericson-j-santos/reqsys-v2-enterprise-real",
            "workflow_inventory": {
                "baseline_count": len(workflow_names),
                "enforce_exact_count": True,
            },
            "domains": [
                {
                    "id": "core",
                    "target_repository": "ericson-j-santos/reqsys-v2-enterprise-real",
                    "migration_state": "retain",
                    "workflow_globs": [],
                },
                {
                    "id": "ci-platform",
                    "target_repository": "ericson-j-santos/reqsys-ci-platform",
                    "migration_state": "prepared",
                    "workflow_globs": [],
                },
                {
                    "id": "bacen",
                    "target_repository": "ericson-j-santos/reqsys-governance-bacen",
                    "migration_state": "prepared_for_shadow_copy",
                    "workflow_globs": ["bacen-*.yml"],
                    "workflow_files": bacen,
                    "inventory_baseline_count": len(bacen),
                },
                {
                    "id": "m365",
                    "target_repository": "ericson-j-santos/reqsys-integrations-m365",
                    "migration_state": "planned",
                    "workflow_globs": ["teams-*.yml"],
                },
                {
                    "id": "runtime-platform",
                    "target_repository": "ericson-j-santos/reqsys-runtime-platform",
                    "migration_state": "planned",
                    "workflow_globs": ["runtime-*.yml"],
                },
                {
                    "id": "product-intelligence",
                    "target_repository": "ericson-j-santos/reqsys-product-intelligence",
                    "migration_state": "planned",
                    "workflow_globs": ["product-intelligence-*.yml"],
                },
            ],
        }

    def test_accepts_exact_inventory(self) -> None:
        names = ["ci.yml", "bacen-a.yml", "bacen-b.yml", "teams-a.yml"]
        root = self._root(names)
        errors, summary = validate_inventory(root, self._payload(names))
        self.assertEqual(errors, [])
        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["domains"]["bacen"]["matched_workflows"], 2)

    def test_blocks_global_workflow_count_drift(self) -> None:
        names = ["ci.yml", "bacen-a.yml"]
        root = self._root(names)
        payload = self._payload(names)
        payload["workflow_inventory"]["baseline_count"] = 99
        errors, _ = validate_inventory(root, payload)
        self.assertTrue(any("workflow inventory drift" in item for item in errors))

    def test_blocks_bacen_manifest_drift(self) -> None:
        names = ["ci.yml", "bacen-a.yml", "bacen-b.yml"]
        root = self._root(names)
        payload = self._payload(names)
        payload["domains"][2]["workflow_files"] = ["bacen-a.yml"]
        errors, _ = validate_inventory(root, payload)
        self.assertTrue(any("bacen: workflow inventory mismatch" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
