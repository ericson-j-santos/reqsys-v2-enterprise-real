"""Offline workflow contract for scripts/native_postgres_ci.py and CI.

No YAML dependency or subprocess is needed. The existing Pre-PR selector finds
this file by the script/workflow references, as well as its SDD declaration.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
HELPER = ROOT / "scripts/native_postgres_ci.py"


def backend_job(workflow: str) -> str:
    start = workflow.index("\n  backend-test:\n")
    end = workflow.index("\n  frontend-build:\n", start)
    return workflow[start:end]


def violations(workflow: str) -> list[str]:
    block = backend_job(workflow)
    required = (
        "name: Backend Tests + Coverage (pytest)",
        "runs-on: ubuntu-24.04",
        "timeout-minutes: 35",
        "needs: [ci-router, ci-budget-guard]",
        "if: needs.ci-router.outputs.backend == 'true' || needs.ci-router.outputs.full_ci == 'true'",
        'python-version: "3.12"',
        "working-directory: backend",
        "Install ODBC driver (pyodbc dependency)",
        "install -y --no-install-recommends unixodbc-dev",
        "pip install -r requirements.txt",
        "Verificar encoding UTF-8 (anti-mojibake)",
        "python -m unittest discover -s tests -p 'test_native_postgres_ci*.py' -v",
        "set -euo pipefail",
        "trap cleanup EXIT",
        "trap 'exit 130' INT",
        "trap 'exit 143' TERM",
        'source "$env_file"',
        'python ../scripts/native_postgres_ci.py exercise --state "$state"',
        'python ../scripts/native_postgres_ci.py probe --state "$state"',
        "python -m pytest tests/ -v --tb=short",
        "--cov=app",
        "--cov-config=pyproject.toml",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=xml:/tmp/backend-coverage.xml",
        "--cov-fail-under=60 2>&1 | tee /tmp/backend-pytest-output.log",
        "name: backend-pytest-coverage-report",
        "artifacts/native-postgres/receipt.json",
    )
    errors = ["missing:" + value for value in required if value not in block]
    forbidden = ("    services:", "postgres:16-alpine", "ci-postgres-password",
                 "DATABASE_URL:", "continue-on-error:", "PGPASSWORD", "systemctl", "pg_ctlcluster")
    errors.extend("forbidden:" + value for value in forbidden if value in block)
    if not re.search(r"name: Clean up only the owned native PostgreSQL cluster\n"
                     r"\s+if: always\(\)\n", block):
        errors.append("cleanup_must_always_run")
    if not re.search(r"name: Publish sanitized native PostgreSQL receipt\n"
                     r"\s+if: always\(\)\n", block):
        errors.append("receipt_must_always_run")
    if not re.search(r"name: Publicar relatório pytest/cobertura\n"
                     r"\s+if: always\(\)\n", block):
        errors.append("coverage_artifact_must_always_run")
    # A helper failure may not be swallowed by a successful tee or cleanup.
    if 'if ! python ../scripts/native_postgres_ci.py cleanup --state "$state"; then\n' not in block:
        errors.append("cleanup_failure_not_propagated")
    if "native_postgres_ci.py exercise" in block and "python -m pytest tests/" in block and block.index("native_postgres_ci.py exercise") > block.index("python -m pytest tests/"):
        errors.append("exercise_must_precede_suite")
    if "--cov-config=pyproject.toml" in block and "--cov-report=" in block and block.index("--cov-config=pyproject.toml") > block.index("--cov-report="):
        errors.append("explicit_coverage_config_required_first")
    return errors


class NativePostgresWorkflowContractTests(unittest.TestCase):
    def test_workflow_contract(self):
        self.assertEqual(violations(WORKFLOW.read_text(encoding="utf-8")), [])

    def test_control_detects_original_docker_service_and_missing_negative(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        for changed in (
            source.replace("    runs-on: ubuntu-24.04", "    runs-on: ubuntu-latest"),
            source.replace("    timeout-minutes: 35", "    services:\n      postgres:\n        image: postgres:16-alpine"),
            source.replace('python ../scripts/native_postgres_ci.py exercise --state "$state"', "true"),
            source.replace("--cov-fail-under=60", "--cov-fail-under=0"),
            source.replace("python -m pytest tests/ -v", "python -m pytest tests/test_auth.py -v"),
            source.replace("--cov-config=pyproject.toml", ""),
            source.replace("trap cleanup EXIT", "true"),
            source.replace("name: Clean up only the owned native PostgreSQL cluster\n        if: always()",
                           "name: Clean up only the owned native PostgreSQL cluster\n        if: success()"),
        ):
            with self.subTest(changed=changed != source):
                self.assertTrue(violations(changed))

    def test_expected_job_names_and_gates_remain(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        marker = "\njobs:\n"
        self.assertIn(marker, source)
        jobs = source.split(marker, 1)[1]
        self.assertEqual(re.findall(r"^  ([a-z][a-z0-9-]+):$", jobs, re.MULTILINE), [
            "ci-admission", "ci-router",
            "ci-budget-guard", "backend-lint", "backend-test", "frontend-build",
            "frontend-e2e-responsive", "deploy-check-wrapper-powershell-51",
            "pipeline-governance", "ci-result",
        ])
        for unchanged in (
            "name: CI Admission Controller", "name: CI Router (paths + Pareto)",
            "name: CI Budget Guard", "name: CI Router Result",
            "name: Pipeline Governança + Evidence Snapshot", "needs: ci-admission",
            "python scripts/ci_admission_guard.py", "python scripts/ci_budget_guard.py",
        ):
            self.assertIn(unchanged, source)

    def test_artifact_allowlist_excludes_fixture_and_database_secrets(self):
        block = backend_job(WORKFLOW.read_text(encoding="utf-8"))
        uploads = block[block.index("      - name: Publish sanitized") :]
        for forbidden in ("RUNNER_TEMP", "pgpass", "postgres.log", "owner.json", "*.json", "**"):
            self.assertNotIn(forbidden, uploads)
        self.assertIn("/tmp/backend-pytest-output.log", uploads)
        self.assertIn("/tmp/backend-coverage.xml", uploads)

    def test_helper_has_no_install_system_service_or_database_fallback(self):
        source = HELPER.read_text(encoding="utf-8")
        for forbidden in ("shell=True", 'command("sudo"', "systemctl ", "pg_ctlcluster ",
                          "apt-get ", "docker run ", "sqlite://", "trust\n"):
            self.assertNotIn(forbidden, source)
        self.assertIn('BIN = Path("/usr/lib/postgresql/16/bin")', source)
        self.assertIn('os.geteuid() != 0', source)
        self.assertIn('ready_exit == 2 and sql_exit == 2', source)
        self.assertIn('160000 <= int(fields[1]) < 170000', source)


if __name__ == "__main__":
    unittest.main()
