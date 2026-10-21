from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.powerbi_template_runtime_resolver import (
    FABRIC_BASE,
    POWERBI_BASE,
    SENTINEL,
    TEMPLATE_ALIASES,
    ResolverError,
    _matching_templates,
    _normalize_name,
    _validate_url,
    resolve_runtime,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "fabric-oidc-readonly-probe.yml"
SCRIPT = ROOT / "scripts" / "powerbi_template_runtime_resolver.py"


class FakeFabricRequester:
    def __init__(self, role="Contributor", status=200, role_assignments_status=None):
        self.role = role
        self.status = status
        self.role_assignments_status = status if role_assignments_status is None else role_assignments_status
        self.calls = []

    def __call__(self, method, url, token, payload):
        self.calls.append((method, url, payload))
        if url.startswith(FABRIC_BASE + "/workspaces?roles="):
            if self.status != 200:
                return self.status, {}
            requested = url.rsplit("=", 1)[-1]
            values = []
            if self.role == requested:
                values.append({
                    "id": "11111111-1111-1111-1111-111111111111",
                    "displayName": "segredo-fabric-workspace",
                })
            return 200, {"value": values}
        if url.startswith(FABRIC_BASE + "/workspaces/") and url.endswith("/roleAssignments"):
            if self.role_assignments_status != 200:
                return self.role_assignments_status, {}
            values = []
            if self.role is not None:
                values.append({
                    "id": "99999999-9999-9999-9999-999999999999",
                    "principal": {
                        "id": "88888888-8888-8888-8888-888888888888",
                        "type": "ServicePrincipal",
                        "displayName": "segredo-fabric",
                        "servicePrincipalDetails": {
                            "aadAppId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                        },
                    },
                    "role": self.role,
                })
            return 200, {"value": values}
        raise AssertionError(url)


class FakeRequester:
    def __init__(
        self, *, dre=True, ambiguous=False, execute_status=200, execute_value=0,
        principal_role="Contributor", dedicated=False, read_only=False,
        sentinel=False, sentinel_report_alias=False,
    ):
        self.calls = []
        self.dre = dre
        self.ambiguous = ambiguous
        self.execute_status = execute_status
        self.execute_value = execute_value
        self.principal_role = principal_role
        self.dedicated = dedicated
        self.read_only = read_only
        self.sentinel = sentinel
        self.sentinel_report_alias = sentinel_report_alias

    def __call__(self, method, url, token, payload):
        self.calls.append((method, url, payload))
        if url == POWERBI_BASE + "/groups?$top=100&$skip=0":
            return 200, {"value": [{
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "segredo",
                "isReadOnly": self.read_only,
                "isOnDedicatedCapacity": self.dedicated,
            }]}
        if url.endswith("/reports"):
            values = []
            if self.dre:
                values.append({
                    "id": "22222222-2222-2222-2222-222222222222",
                    "name": "1. Dashboard DRE",
                    "datasetId": "33333333-3333-3333-3333-333333333333",
                })
            if self.sentinel:
                values.append({
                    "id": "66666666-6666-6666-6666-666666666666",
                    "name": (
                        "1. Dashboard DRE" if self.sentinel_report_alias
                        else "ReqSys DRE Sentinel DEV"
                    ),
                    "datasetId": "77777777-7777-7777-7777-777777777777",
                })
            if self.ambiguous:
                values.append({
                    "id": "44444444-4444-4444-4444-444444444444",
                    "name": "DRE",
                    "datasetId": "55555555-5555-5555-5555-555555555555",
                })
            return 200, {"value": values}
        if url.endswith("/users"):
            values = []
            if self.principal_role is not None:
                values.append({
                    "identifier": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "principalType": "App",
                    "groupUserAccessRight": self.principal_role,
                    "displayName": "segredo-app",
                })
            return 200, {"value": values}
        if url.endswith("/datasets"):
            values = []
            if self.dre:
                values.append({
                    "id": "33333333-3333-3333-3333-333333333333",
                    "name": "DRE",
                })
            if self.sentinel:
                values.append({
                    "id": "77777777-7777-7777-7777-777777777777",
                    "name": "ReqSys DRE Sentinel DEV",
                })
            if self.ambiguous:
                values.append({
                    "id": "55555555-5555-5555-5555-555555555555",
                    "name": "Dashboard DRE",
                })
            return 200, {"value": values}
        if url.endswith("/executeQueries"):
            if self.execute_status != 200:
                return self.execute_status, {}
            return 200, {"results": [{"tables": [{"rows": [{"[value]": self.execute_value}]}]}]}
        raise AssertionError(url)


class TestPowerBiTemplateRuntimeResolver(unittest.TestCase):
    def test_normalizacao_e_aliases_sao_deterministicos(self):
        self.assertEqual(_normalize_name("9. Produção - V2.pbix"), "9 producao v2")
        self.assertEqual(set(TEMPLATE_ALIASES), {
            "dre", "rh", "estoque", "sac", "logistica", "financeiro", "comercial",
            "producao", "producao_v2", "compras", "compras_v2",
        })

    def test_assinatura_de_dominio_aceita_decoracao_sem_fuzzy(self):
        self.assertEqual(_matching_templates(_normalize_name("ReqSys - Dashboard Financeiro - DEV")),
                         [("financeiro", "domain_signature")])
        self.assertEqual(_matching_templates(_normalize_name("Relatório Produção V2 HML")),
                         [("producao_v2", "domain_signature")])
        self.assertEqual(_matching_templates(_normalize_name("Relatório Produção HML")),
                         [("producao", "domain_signature")])
        self.assertEqual(_matching_templates(_normalize_name("ReqSys Observabilidade")), [])

    def test_sentinel_dre_nao_pode_casar_com_template_de_negocio(self):
        self.assertEqual(
            _matching_templates(_normalize_name("ReqSys DRE Sentinel DEV")), []
        )

    def test_sentinel_sozinho_nao_cria_binding_e_nao_executa_dax(self):
        fake = FakeRequester(
            dre=False, sentinel=True, sentinel_report_alias=True
        )
        result = resolve_runtime(token="x", requester=fake)
        dre = next(x for x in result["bindings"] if x["template_id"] == "dre")
        self.assertEqual(dre["status"], "unmatched")
        self.assertEqual(result["inventory"]["semantic_model_count"], 1)
        self.assertEqual(
            result["sentinel_parity"]["blocker"], "dre_binding_unresolved"
        )
        self.assertFalse(
            any(url.endswith("/executeQueries") for _, url, _ in fake.calls)
        )

    def test_dre_real_com_sentinel_nao_fica_ambiguo(self):
        fake = FakeRequester(
            dre=True, sentinel=True, sentinel_report_alias=True
        )
        result = resolve_runtime(token="x", requester=fake)
        dre = next(x for x in result["bindings"] if x["template_id"] == "dre")
        self.assertEqual(dre["status"], "resolved")
        self.assertEqual(result["binding_summary"], {"resolved": 1, "unmatched": 10})
        query_urls = [
            url for _, url, _ in fake.calls if url.endswith("/executeQueries")
        ]
        self.assertEqual(len(query_urls), 1)
        self.assertIn("/datasets/33333333-3333-3333-3333-333333333333/", query_urls[0])
        self.assertNotIn("77777777-7777-7777-7777-777777777777", query_urls[0])
        self.assertFalse(result["metric_parity_promoted"])

    def test_resolve_dre_e_executa_sentinel_sem_persistir_ids_nomes(self):
        fake = FakeRequester()
        result = resolve_runtime(
            token="x",
            principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            requester=fake,
            fabric_token="fabric-x",
            fabric_requester=FakeFabricRequester(),
        )
        dre = next(item for item in result["bindings"] if item["template_id"] == "dre")
        self.assertEqual(dre["status"], "resolved")
        self.assertRegex(dre["workspace_ref"], r"^[0-9a-f]{24}$")
        self.assertRegex(dre["semantic_model_ref"], r"^[0-9a-f]{24}$")
        self.assertEqual(result["sentinel_parity"]["status"], "passed")
        self.assertEqual(result["sentinel_parity"]["powerbi_value"], 0)
        self.assertFalse(result["sentinel_parity"]["promotes_metric_parity"])
        serialized = json.dumps(result, ensure_ascii=False)
        for raw in (
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
            "segredo",
            "1. Dashboard DRE",
        ):
            self.assertNotIn(raw, serialized)
        self.assertFalse(result["raw_remote_ids_persisted"])
        self.assertFalse(result["raw_remote_names_persisted"])
        self.assertFalse(result["raw_remote_ids_or_names_logged"])

    def test_preflight_observa_role_e_capacidade_sem_inferir_custo_zero(self):
        fake = FakeRequester(principal_role="Contributor", dedicated=False, read_only=False)
        result = resolve_runtime(
            token="x",
            principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            requester=fake,
            fabric_token="fabric-x",
            fabric_requester=FakeFabricRequester(),
        )
        workspace = result["workspace_access"][0]
        self.assertEqual(workspace["powerbi_principal_role"], "Contributor")
        self.assertEqual(workspace["powerbi_principal_role_status"], "observed")
        self.assertEqual(workspace["fabric_principal_role"], "Contributor")
        self.assertEqual(workspace["fabric_principal_role_status"], "observed")
        self.assertEqual(workspace["fabric_role_filter_role"], "Contributor")
        self.assertEqual(workspace["fabric_role_filter_status"], "observed")
        self.assertEqual(workspace["fabric_role_assignments_status"], 200)
        self.assertFalse(workspace["is_read_only"])
        self.assertFalse(workspace["is_on_dedicated_capacity"])
        self.assertTrue(workspace["write_candidate"])
        self.assertEqual(result["publication_preflight"]["write_candidate_count"], 1)
        self.assertFalse(result["publication_preflight"]["new_capacity_or_license_requested"])
        self.assertFalse(result["publication_preflight"]["billing_mutation_performed"])
        self.assertFalse(result["publication_preflight"]["incremental_cost_verified_zero"])

    def test_viewer_ou_workspace_readonly_nao_e_candidato_a_escrita(self):
        for role, read_only in (("Viewer", False), ("Contributor", True), (None, False)):
            with self.subTest(role=role, read_only=read_only):
                result = resolve_runtime(
                    token="x",
                    principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    requester=FakeRequester(
                        principal_role=role, dedicated=False, read_only=read_only
                    ),
                )
                self.assertFalse(result["workspace_access"][0]["write_candidate"])

    def test_fabric_role_pode_confirmar_contributor_quando_powerbi_users_nao_encontra(self):
        result = resolve_runtime(
            token="x",
            principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            fabric_token="fabric-x",
            requester=FakeRequester(principal_role=None),
            fabric_requester=FakeFabricRequester(role="Contributor", role_assignments_status=403),
        )
        workspace = result["workspace_access"][0]
        self.assertIsNone(workspace["powerbi_principal_role"])
        self.assertEqual(workspace["powerbi_principal_role_status"], "not_found")
        self.assertIsNone(workspace["fabric_principal_role"])
        self.assertEqual(workspace["fabric_principal_role_status"], "forbidden")
        self.assertEqual(workspace["fabric_role_filter_role"], "Contributor")
        self.assertEqual(workspace["fabric_role_filter_status"], "observed")
        self.assertTrue(workspace["write_candidate"])

    def test_fabric_role_403_nao_vira_permissao_por_inferencia(self):
        result = resolve_runtime(
            token="x",
            principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            fabric_token="fabric-x",
            requester=FakeRequester(principal_role=None),
            fabric_requester=FakeFabricRequester(role=None, status=403, role_assignments_status=403),
        )
        workspace = result["workspace_access"][0]
        self.assertEqual(workspace["fabric_principal_role_status"], "forbidden")
        self.assertIsNone(workspace["fabric_principal_role"])
        self.assertFalse(workspace["write_candidate"])

    def test_binding_ambiguo_falha_fechado_e_nao_executa_query(self):
        fake = FakeRequester(ambiguous=True)
        result = resolve_runtime(
            token="x",
            principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            requester=fake,
            fabric_token="fabric-x",
            fabric_requester=FakeFabricRequester(),
        )
        dre = next(item for item in result["bindings"] if item["template_id"] == "dre")
        self.assertEqual(dre["status"], "ambiguous")
        self.assertEqual(dre["candidate_count"], 2)
        self.assertEqual(result["sentinel_parity"]["status"], "blocked")
        self.assertEqual(result["sentinel_parity"]["blocker"], "dre_binding_unresolved")
        self.assertFalse(any(url.endswith("/executeQueries") for _, url, _ in fake.calls))

    def test_execute_queries_403_fica_bloqueado_sem_corpo_remoto(self):
        fake = FakeRequester(execute_status=403)
        result = resolve_runtime(
            token="x",
            principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            requester=fake,
            fabric_token="fabric-x",
            fabric_requester=FakeFabricRequester(),
        )
        sentinel = result["sentinel_parity"]
        self.assertEqual(sentinel["status"], "blocked")
        self.assertEqual(sentinel["blocker"], "execute_queries_not_available")
        self.assertEqual(sentinel["http_status"], 403)
        self.assertNotIn("error", sentinel)

    def test_sentinel_detecta_divergencia_e_nao_promove_paridade(self):
        fake = FakeRequester(execute_value=1)
        result = resolve_runtime(
            token="x",
            principal_identifier="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            requester=fake,
            fabric_token="fabric-x",
            fabric_requester=FakeFabricRequester(),
        )
        self.assertEqual(result["sentinel_parity"]["status"], "failed")
        self.assertFalse(result["metric_parity_promoted"])
        self.assertFalse(SENTINEL["representative_business_metric"])

    def test_endpoint_post_so_permite_execute_queries(self):
        _validate_url(
            "POST",
            POWERBI_BASE
            + "/groups/11111111-1111-1111-1111-111111111111"
            + "/datasets/33333333-3333-3333-3333-333333333333/executeQueries",
        )
        with self.assertRaisesRegex(ResolverError, "method_not_allowed"):
            _validate_url(
                "POST",
                POWERBI_BASE + "/groups/11111111-1111-1111-1111-111111111111/refreshes",
            )

    def test_script_nao_contem_endpoints_de_mutacao(self):
        text = SCRIPT.read_text(encoding="utf-8")
        lowered = text.casefold()
        for forbidden_endpoint in (
            "/imports", "/refreshes", "/tables/", "/rows", "/dashboards", "/semanticmodels",
        ):
            self.assertNotIn(forbidden_endpoint, lowered)
        for forbidden_method in (
            '"DELETE"', '"PATCH"', '"PUT"',
            "method=\"DELETE\"", "method=\"PATCH\"", "method=\"PUT\"",
        ):
            self.assertNotIn(forbidden_method, text)
        self.assertIn("/executeQueries", text)
        self.assertIn("/users", text)

    def test_workflow_oidc_sem_segredo_e_pr_restrito(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("id-token: write", text)
        self.assertIn("contents: read", text)
        self.assertIn("environment: development", text)
        self.assertIn("azure/login@", text)
        self.assertNotIn("client-secret:", text)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", text)
        self.assertIn("github.actor == 'ericson-j-santos'", text)
        self.assertIn("mutations_performed", text)
        self.assertIn("metric_parity_promoted", text)


if __name__ == "__main__":
    unittest.main()
