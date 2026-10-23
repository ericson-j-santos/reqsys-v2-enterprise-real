"""Contratos nativos: no-op não alcança locator, credenciais ou entrega Teams."""

import ast
import copy
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.teams_notification_admission import AdmissionError, classify_workflow_run


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/teams-commit-notification.yml"


def source(name="Ollama CI Triage", conclusion="success"):
    return {"name": name, "conclusion": conclusion, "id": 300}


def triage(result="OLLAMA_CI_TRIAGE_OK"):
    return {
        "schema_version": "1.0.0",
        "run_id": 200,
        "result": result,
        "triage": {"category": "test", "root_cause": "synthetic fixture"},
    }


class TeamsNotificationAdmissionTests(unittest.TestCase):
    def test_skipped_cancelled_neutral_never_load_artifacts(self):
        for name in ("Ollama CI Triage", "PR CI Remediation"):
            for conclusion in ("skipped", "cancelled", "neutral"):
                with self.subTest(name=name, conclusion=conclusion):
                    loader = Mock(side_effect=AssertionError("network must not run"))
                    allowed, reason, payload = classify_workflow_run(
                        source(name, conclusion), loader
                    )
                    self.assertFalse(allowed)
                    self.assertEqual(reason, "source_without_execution")
                    self.assertEqual(payload, {})
                    loader.assert_not_called()

    def test_unsupported_source_never_loads_artifacts(self):
        loader = Mock()
        self.assertFalse(classify_workflow_run(source("Other"), loader)[0])
        loader.assert_not_called()

    def test_source_identity_or_conclusion_invalid_fails_before_fetch(self):
        for payload in (
            {"name": "Ollama CI Triage", "conclusion": None, "id": 300},
            {"name": "Ollama CI Triage", "conclusion": "success", "id": 0},
            {"name": "Ollama CI Triage", "conclusion": "success", "id": True},
        ):
            with self.subTest(payload=payload):
                loader = Mock()
                with self.assertRaises(AdmissionError):
                    classify_workflow_run(payload, loader)
                loader.assert_not_called()

    def test_executed_triage_and_real_degradation_remain_admitted(self):
        for result in (
            "OLLAMA_CI_TRIAGE_OK",
            "OLLAMA_CI_TRIAGE_DEGRADED",
            "OLLAMA_CI_TRIAGE_BLOCKED",
        ):
            with self.subTest(result=result):
                evidence = triage(result)
                loader = Mock(return_value=evidence)
                allowed, reason, received = classify_workflow_run(source(), loader)
                self.assertTrue(allowed)
                self.assertEqual(reason, "executed_triage")
                self.assertEqual(received, evidence)
                loader.assert_called_once_with(300, "ollama-ci-triage-", "evidence.json")

    def test_valid_ok_with_empty_root_cause_preserves_material_notification(self):
        evidence = triage()
        evidence["triage"]["root_cause"] = ""
        evidence["worker_pool"] = {"status": "enqueued"}
        allowed, reason, _ = classify_workflow_run(
            source(), Mock(return_value=evidence)
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "executed_triage")

    def test_blocked_triage_receipt_preserves_real_failure_notification(self):
        evidence = {
            "schema_version": "1.0.0",
            "result": "OLLAMA_CI_TRIAGE_BLOCKED",
            "run_id": 200,
            "reason": "synthetic governance block",
            "execute": True,
        }
        allowed, _, _ = classify_workflow_run(
            source(conclusion="failure"), Mock(return_value=evidence)
        )
        self.assertTrue(allowed)

    def test_absent_empty_or_malformed_evidence_fails_closed(self):
        invalid = (
            None, {}, [], {"schema_version": "99"},
            {"schema_version": "1.0.0", "result": "OLLAMA_CI_TRIAGE_OK", "run_id": 200},
            {**triage(), "result": "unknown"},
            {**triage(), "run_id": None},
            {**triage(), "triage": {"root_cause": "synthetic", "category": ""}},
            {**triage(), "triage": {"root_cause": "synthetic", "category": True}},
            {**triage(), "triage": {"root_cause": "synthetic", "category": "not-real"}},
            {**triage("OLLAMA_CI_TRIAGE_DEGRADED"), "triage": [], "reason": "synthetic"},
        )
        for evidence in invalid:
            with self.subTest(evidence=evidence):
                with self.assertRaises(AdmissionError):
                    classify_workflow_run(source(), Mock(return_value=evidence))

    def test_no_remediation_skips_before_delivery(self):
        report = {"schema_version": "1.0.0", "execute": True, "reruns_executed": 0}
        allowed, reason, payload = classify_workflow_run(
            source("PR CI Remediation"), Mock(return_value=report)
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "no_material_remediation")
        self.assertEqual(payload, {})

    def test_effective_remediation_remains_admitted(self):
        report = {"schema_version": "1.0.0", "execute": True, "reruns_executed": 1}
        loader = Mock(return_value=report)
        allowed, reason, _ = classify_workflow_run(source("PR CI Remediation"), loader)
        self.assertTrue(allowed)
        self.assertEqual(reason, "material_remediation")
        loader.assert_called_once_with(300, "pr-ci-remediation-evidence-", "report.json")

    def test_invalid_or_unverified_remediation_never_admitted(self):
        for count, execute in ((True, True), (-1, True), ("1", True), (None, True), (1, False)):
            with self.subTest(count=count, execute=execute):
                report = {
                    "schema_version": "1.0.0", "execute": execute,
                    "reruns_executed": count,
                }
                with self.assertRaises(AdmissionError):
                    classify_workflow_run(
                        source("PR CI Remediation"), Mock(return_value=report)
                    )

    def test_repeat_is_pure_and_does_not_mutate_receipt(self):
        evidence = triage()
        before = copy.deepcopy(evidence)
        loader = Mock(return_value=evidence)
        first = classify_workflow_run(source(), loader)
        second = classify_workflow_run(source(), loader)
        self.assertEqual(first, second)
        self.assertEqual(evidence, before)

    def test_artifact_error_propagates_before_delivery(self):
        with self.assertRaisesRegex(OSError, "synthetic"):
            classify_workflow_run(source(), Mock(side_effect=OSError("synthetic")))


class TeamsNotificationWorkflowAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.notification = cls.workflow.split("  notify-teams:\n", 1)[1]
        cls.preparation = cls.notification.split(
            "      - name: Classificar e preparar notificação antes de locator e segredos\n", 1
        )[1].split("      - name: Preparar Node para locator DEV assinado\n", 1)[0]

    def test_job_rejects_skipped_before_steps_and_has_no_secret_env(self):
        before_steps = self.notification.split("    steps:\n", 1)[0]
        self.assertIn('["skipped","cancelled","neutral"]', before_steps)
        self.assertIn("github.event.workflow_run.conclusion", before_steps)
        self.assertNotIn("secrets.", before_steps)
        self.assertNotIn("${{ runner.", before_steps)
        self.assertIn("PREPARED_NOTIFICATION: ${{ github.workspace }}/", before_steps)
        # Negative control: an unsupported runner context must fail this guard.
        invalid = before_steps.replace("${{ github.workspace }}", "${{ runner.temp }}")
        self.assertIn("${{ runner.", invalid)

    def test_admission_precedes_locator_and_has_no_delivery_secret(self):
        self.assertNotIn("secrets.", self.preparation)
        self.assertNotIn("resolve_pc24x7_dev_locator", self.preparation)
        self.assertNotIn("scripts/notificar_teams.py", self.preparation)
        self.assertNotIn("send-webhook", self.preparation)
        self.assertIn("classify_workflow_run(source, artifact_json)", self.preparation)
        self.assertLess(
            self.notification.index("id: admission"),
            self.notification.index("id: locator"),
        )

    def test_every_locator_secret_and_delivery_step_is_gated(self):
        guarded = (
            "Preparar Node para locator DEV assinado",
            "Validar gateway",
            "Validar locator PC24x7 fail-closed",
            "Resolver runtime PC24x7 DEV vigente",
            "Exportar Teams Gateway efêmero",
            "Validar configuração do Teams",
            "Enviar notificação",
        )
        for name in guarded:
            with self.subTest(name=name):
                block = self.notification.split("      - name: " + name + "\n", 1)[1]
                block = block.split("      - name: ", 1)[0]
                self.assertIn("if:", block)
                self.assertIn("steps.admission.outputs.notify == 'true'", block)
        delivery = self.notification.split("      - name: Enviar notificação\n", 1)[1]
        delivery = delivery.split("      - name: Registrar evidência\n", 1)[0]
        self.assertNotIn("artifact_json(", delivery)
        self.assertIn('prepared_path.read_text(encoding="utf-8")', delivery)
        self.assertIn("prepared_path.unlink()", delivery)

    def preparation_code(self):
        script = self.preparation.split("          python - <<'PY'\n", 1)[1]
        script = script.split("\n          PY\n", 1)[0]
        return "\n".join(line[10:] if line.startswith("          ") else line for line in script.splitlines())

    def run_preparation(self, event, urlopen=None, opener=None, expect_notify=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_path = root / "event.json"
            output_path = root / "outputs"
            prepared_path = root / "prepared.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            env = {
                "EVENT_PATH": str(event_path), "EVENT_NAME": "workflow_run",
                "REPOSITORY": "example/repository", "SHA": "a" * 40,
                "SERVER_URL": "https://github.com", "RUN_ID": "400",
                "GITHUB_OUTPUT": str(output_path),
                "PREPARED_NOTIFICATION": str(prepared_path),
                "GITHUB_TOKEN": "synthetic-github-only",
            }
            if urlopen is None:
                urlopen = Mock(side_effect=AssertionError("no network for skipped"))
            if opener is None:
                opener = Mock()
                opener.open.side_effect = AssertionError("no archive for skipped")
            with patch.dict(os.environ, env, clear=True), patch(
                "urllib.request.urlopen", urlopen
            ), patch("urllib.request.build_opener", return_value=opener):
                if expect_notify:
                    exec(compile(self.preparation_code(), "workflow-preparation", "exec"), {})
                else:
                    with self.assertRaises(SystemExit) as exit_result:
                        exec(compile(self.preparation_code(), "workflow-preparation", "exec"), {})
                    self.assertEqual(exit_result.exception.code, 0)
            self.assertEqual(prepared_path.exists(), expect_notify)
            prepared = (
                json.loads(prepared_path.read_text(encoding="utf-8"))
                if expect_notify else None
            )
            return output_path.read_text(encoding="utf-8"), urlopen, opener, prepared

    def test_real_inline_artifact_allowlist_blocks_unrecognized_contract(self):
        module = ast.parse(self.preparation_code())
        function = next(
            item for item in module.body
            if isinstance(item, ast.FunctionDef) and item.name == "artifact_json"
        )
        github_json = Mock(side_effect=AssertionError("no network before admission"))
        namespace = {"github_json": github_json}
        exec(compile(ast.Module(body=[function], type_ignores=[]),
                     "artifact-contract", "exec"), namespace)
        with self.assertRaisesRegex(ValueError, "artifact_contract_not_supported"):
            namespace["artifact_json"](300, "unrecognized-", "private.json")
        github_json.assert_not_called()

    def test_real_inline_preparation_skipped_never_accesses_network(self):
        output, urlopen, opener, _ = self.run_preparation(
            {"workflow_run": source(conclusion="skipped")}
        )
        self.assertIn("notify=false", output)
        self.assertIn("reason=source_without_execution", output)
        urlopen.assert_not_called()
        opener.open.assert_not_called()

    def test_real_inline_preparation_noop_remediation_has_no_delivery_payload(self):
        report = {"schema_version": "1.0.0", "execute": True, "reruns_executed": 0}
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("report.json", json.dumps(report))
        metadata = {
            "artifacts": [{
                "id": 1, "name": "pr-ci-remediation-evidence-300",
                "expired": False,
                "archive_download_url": "https://api.github.com/synthetic-artifact",
            }]
        }
        request = Mock(return_value=io.BytesIO(json.dumps(metadata).encode()))
        opener = Mock()
        opener.open.return_value = io.BytesIO(archive.getvalue())
        output, _, _, _ = self.run_preparation(
            {"workflow_run": source("PR CI Remediation")}, request, opener
        )
        self.assertIn("notify=false", output)
        self.assertIn("reason=no_material_remediation", output)


    def test_real_inline_preparation_material_receipts_render_without_delivery(self):
        receipts = (
            ("Ollama CI Triage", "ollama-ci-triage-", "evidence.json", triage()),
            ("PR CI Remediation", "pr-ci-remediation-evidence-", "report.json",
             {"schema_version": "1.0.0", "execute": True, "reruns_executed": 1}),
        )
        for name, prefix, filename, receipt in receipts:
            with self.subTest(name=name):
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr(filename, json.dumps(receipt))
                metadata = {"artifacts": [{
                    "id": 1, "name": prefix + "300", "expired": False,
                    "archive_download_url": "https://api.github.com/synthetic-artifact",
                }]}
                request = Mock(return_value=io.BytesIO(json.dumps(metadata).encode()))
                opener = Mock()
                opener.open.return_value = io.BytesIO(archive.getvalue())
                output, _, _, prepared = self.run_preparation(
                    {"workflow_run": source(name)}, request, opener, expect_notify=True
                )
                self.assertIn("notify=true", output)
                self.assertEqual(
                    set(prepared), {"title", "subtitle", "facts", "actions", "message"}
                )
                self.assertTrue(prepared["title"])
                self.assertTrue(prepared["message"])
                request.assert_called_once()
                opener.open.assert_called_once()

    def test_real_inline_preparation_missing_receipt_fails_before_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_path = root / "event.json"
            output_path = root / "outputs"
            prepared_path = root / "prepared.json"
            event_path.write_text(json.dumps({"workflow_run": source()}), encoding="utf-8")
            request = Mock(return_value=io.BytesIO(b'{"artifacts": []}'))
            with patch.dict(os.environ, {
                "EVENT_PATH": str(event_path), "EVENT_NAME": "workflow_run",
                "REPOSITORY": "example/repository", "SHA": "a" * 40,
                "SERVER_URL": "https://github.com", "RUN_ID": "400",
                "GITHUB_OUTPUT": str(output_path),
                "PREPARED_NOTIFICATION": str(prepared_path),
                "GITHUB_TOKEN": "synthetic-github-only",
            }, clear=True), patch("urllib.request.urlopen", request):
                with self.assertRaises(AdmissionError):
                    exec(compile(self.preparation_code(), "workflow-preparation", "exec"), {})
            self.assertFalse(prepared_path.exists())
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
