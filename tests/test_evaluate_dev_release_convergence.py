"""Testes positivos, negativos e de repetição para o controle de release DEV."""
from datetime import datetime, timedelta, timezone
import unittest

from scripts.evaluate_dev_release_convergence import ContractError, evaluate

NOW = datetime(2026, 11, 3, 16, 0, tzinfo=timezone.utc)
ONE = "1" * 40
TWO = "2" * 40
THREE = "3" * 40


def payload(**changes):
    sample = {
        "schema_version": 1, "environment": "dev",
        "main_sha": ONE, "approved_release_sha": ONE,
        "approval_run_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/41668421364",
        "approval_readback_verified": True, "observed_sha": ONE,
        "observed_at": NOW.isoformat(), "signed_locator_verified": True,
        "independent_runtime_readback": True, "runtime_kind": "native",
        "native_runner_ready": True, "backup_verified": True,
        "rollback_verified": True, "deploy_authorized": False,
    }
    sample.update(changes)
    return sample


class ReleaseConvergenceTests(unittest.TestCase):
    def test_release_aprovada_e_instalada_convergem(self):
        actual = evaluate(payload(), now=NOW)
        self.assertEqual(actual["state"], "RELEASE_CONVERGED")
        self.assertTrue(actual["release_effect_verified"])
        self.assertFalse(actual["automatic_deploy"])

    def test_main_pode_avancar_sem_falsear_release_aprovada(self):
        actual = evaluate(payload(main_sha=THREE), now=NOW)
        self.assertEqual(actual["state"], "RELEASE_CONVERGED")
        self.assertTrue(actual["main_differs_from_approved_release"])
        self.assertEqual(actual["approved_release_sha"], ONE)

    def test_drift_exige_autorizacao_antes_de_publicar(self):
        actual = evaluate(payload(observed_sha=TWO), now=NOW)
        self.assertEqual(actual["state"], "DEPLOY_BLOCKED")
        self.assertIn("deploy_authorization_missing", actual["blockers"])
        self.assertFalse(actual["release_effect_verified"])

    def test_pronto_para_deploy_nao_prova_deploy(self):
        actual = evaluate(payload(observed_sha=TWO, deploy_authorized=True), now=NOW)
        self.assertEqual(actual["state"], "READY_FOR_GOVERNED_DEPLOY")
        self.assertFalse(actual["release_effect_verified"])
        self.assertFalse(actual["automatic_deploy"])

    def test_rejeita_docker_sem_executar(self):
        actual = evaluate(payload(observed_sha=TWO, runtime_kind="docker", deploy_authorized=True), now=NOW)
        self.assertEqual(actual["state"], "DEPLOY_BLOCKED")
        self.assertIn("native_deploy_route_required", actual["blockers"])

    def test_runtime_docker_alinhado_nao_e_considerado_convergente(self):
        actual = evaluate(payload(runtime_kind="docker"), now=NOW)
        self.assertEqual(actual["state"], "DEPLOY_BLOCKED")
        self.assertFalse(actual["release_effect_verified"])
        self.assertIn("native_deploy_route_required", actual["blockers"])

    def test_replay_ignora_avanco_da_main_sem_novo_release(self):
        first = evaluate(payload(observed_sha=TWO), now=NOW)
        second = evaluate(payload(observed_sha=TWO, main_sha=THREE), now=NOW)
        self.assertEqual(first["fingerprint_sha256"], second["fingerprint_sha256"])
        self.assertTrue(second["main_differs_from_approved_release"])

    def test_rejeita_schema_booleano(self):
        with self.assertRaises(ContractError):
            evaluate(payload(schema_version=True), now=NOW)

    def test_rejeita_runner_sem_capacidade(self):
        actual = evaluate(payload(observed_sha=TWO, native_runner_ready=False, deploy_authorized=True), now=NOW)
        self.assertIn("native_runner_unavailable", actual["blockers"])

    def test_rejeita_falta_backup_e_rollback(self):
        actual = evaluate(payload(observed_sha=TWO, backup_verified=False, rollback_verified=False, deploy_authorized=True), now=NOW)
        self.assertIn("backup_unverified", actual["blockers"])
        self.assertIn("rollback_unverified", actual["blockers"])

    def test_rejeita_leitura_nao_independente(self):
        actual = evaluate(payload(independent_runtime_readback=False), now=NOW)
        self.assertEqual(actual["state"], "BLOCKED_NO_EVIDENCE")

    def test_rejeita_fonte_aprovacao_nao_comprovada(self):
        actual = evaluate(payload(approval_readback_verified=False), now=NOW)
        self.assertEqual(actual["state"], "BLOCKED_NO_EVIDENCE")

    def test_rejeita_observacao_antiga(self):
        actual = evaluate(payload(observed_at=(NOW-timedelta(minutes=16)).isoformat()), now=NOW)
        self.assertEqual(actual["state"], "BLOCKED_NO_EVIDENCE")
        self.assertIn("runtime_evidence_stale_or_future", actual["blockers"])

    def test_rejeita_ambiente_prod(self):
        with self.assertRaises(ContractError):
            evaluate(payload(environment="prod"), now=NOW)

    def test_rejeita_sha_invalido(self):
        with self.assertRaises(ContractError):
            evaluate(payload(main_sha="main"), now=NOW)

    def test_rejeita_campos_extra_e_bool_invalido(self):
        with self.assertRaises(ContractError):
            evaluate(payload(dangerous_shell="powershell"), now=NOW)
        with self.assertRaises(ContractError):
            evaluate(payload(deploy_authorized="true"), now=NOW)

    def test_replay_idempotente_nao_cria_novos_efeitos(self):
        first = evaluate(payload(observed_sha=TWO), now=NOW)
        second = evaluate(payload(observed_sha=TWO), now=NOW)
        self.assertEqual(first, second)
        self.assertRegex(first["fingerprint_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
