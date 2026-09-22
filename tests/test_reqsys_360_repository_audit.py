import json
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'reqsys_360_repository_audit.py'
spec = spec_from_file_location('reqsys_360_repository_audit', MODULE_PATH)
audit = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


class ReqSys360RepositoryAuditTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name)
        (repo / 'frontend/src/views').mkdir(parents=True)
        (repo / 'frontend/src/components').mkdir(parents=True)
        (repo / 'frontend/src/services').mkdir(parents=True)
        (repo / 'frontend/src/router').mkdir(parents=True)
        (repo / 'backend/app/api').mkdir(parents=True)
        (repo / 'governance/reqsys-360').mkdir(parents=True)
        return temp, repo

    def test_concilia_consumidor_frontend_com_rota_backend_dinamica(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / 'frontend/src/services/api.js').write_text("fetch('/api/requisitos/123')", encoding='utf-8')
        (repo / 'backend/app/api/requisitos.py').write_text(
            "from fastapi import APIRouter\nrouter = APIRouter(prefix='/api/requisitos')\n@router.get('/{id}')\ndef get(id: str): pass\n",
            encoding='utf-8',
        )
        consumers = audit.frontend_api_consumers(repo)
        routes = audit.backend_routes(repo)
        self.assertEqual(consumers[0]['path'], '/api/requisitos/123')
        self.assertTrue(audit.path_matches(consumers[0]['path'], [item['path'] for item in routes]))

    def test_ignora_frontend_de_testes_no_inventario_de_api(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        test_dir = repo / 'frontend/src/views/__tests__'
        test_dir.mkdir(parents=True)
        (test_dir / 'Fake.spec.js').write_text("fetch('/api/fake')", encoding='utf-8')
        self.assertEqual(audit.frontend_api_consumers(repo), [])

    def test_valida_contrato_de_responsabilidade_sem_duplicidade(self):
        valid = {
            'routes': [
                {'route': '/', 'area': 'trabalho', 'status': 'canonical', 'responsibility': 'Painel'},
                {'route': '/analytics', 'area': 'indicadores', 'status': 'canonical', 'responsibility': 'Indicadores'},
            ],
            'navigation_duplicate_decisions': [
                {'route': '/analytics', 'classification': 'intentional', 'rationale': 'atalho'},
            ],
            'component_reuse_decisions': [
                {'component': 'Shell', 'paths': ['/a', '/b'], 'classification': 'intentional', 'rationale': 'shell'},
            ],
        }
        self.assertEqual(audit.validate_governance(valid), [])
        invalid = {'routes': valid['routes'] + [valid['routes'][1]]}
        codes = [item['code'] for item in audit.validate_governance(invalid)]
        self.assertIn('GOVERNANCE_ROUTE_DUPLICATE', codes)

    def test_estado_de_ui_delegado_a_componente_local_e_detectado(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / 'frontend/src/router/index.js').write_text(
            "import HomeView from '../views/HomeView.vue'\nexport const routes = [\n  { path: '/', component: HomeView }\n]\n",
            encoding='utf-8',
        )
        (repo / 'frontend/src/views/HomeView.vue').write_text(
            "<template><SharedPanel /></template>\n<script setup>import SharedPanel from '../components/SharedPanel.vue'</script>",
            encoding='utf-8',
        )
        (repo / 'frontend/src/components/SharedPanel.vue').write_text(
            "<template><p v-if=\"carregando\">Carregando</p><p v-if=\"erro\">{{ erro }}</p></template>\n"
            "<script setup>import { api } from '../services/api'; async function carregar(){ await api.get('/api/x') }</script>",
            encoding='utf-8',
        )
        items = audit.ui_state_inventory(repo)
        self.assertEqual(items[0]['kind'], 'dynamic')
        self.assertTrue(items[0]['states']['loading'])
        self.assertTrue(items[0]['states']['error'])
        self.assertGreaterEqual(items[0]['state_count'], 2)
        self.assertIn('frontend/src/components/SharedPanel.vue', items[0]['inspected_files'])

    def test_pagina_estatica_nao_recebe_falso_aviso_de_estados(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / 'frontend/src/router/index.js').write_text(
            "import HomeView from '../views/HomeView.vue'\nexport const routes = [\n  { path: '/', component: HomeView }\n]\n",
            encoding='utf-8',
        )
        (repo / 'frontend/src/views/HomeView.vue').write_text('<template><h1>Mapa estático</h1></template>', encoding='utf-8')
        (repo / 'governance/reqsys-360/route-responsibilities.json').write_text(
            json.dumps({'routes': [{'route': '/', 'area': 'trabalho', 'status': 'canonical', 'responsibility': 'Painel'}]}),
            encoding='utf-8',
        )
        (repo / 'governance/reqsys-360/journeys.json').write_text(json.dumps({'journeys': []}), encoding='utf-8')
        report = audit.generate_report(repo)
        self.assertEqual(report['summary']['critical'], 0)
        self.assertEqual(report['summary']['ui_routes'], 1)
        self.assertEqual(report['summary']['ui_dynamic_routes'], 0)
        self.assertEqual(report['summary']['ui_routes_low_state_coverage'], 0)
        self.assertFalse(any(item['code'] == 'UI_STATE_COVERAGE_LOW' for item in report['findings']))

    def test_jornada_mutavel_exige_controles_sem_promover_mock_a_real(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        evidence = repo / 'tests/test_flow.py'
        evidence.parent.mkdir(parents=True)
        evidence.write_text('def test_flow(): pass', encoding='utf-8')
        payload = {
            'journeys': [{
                'id': 'flow',
                'name': 'Fluxo',
                'entry': '/x',
                'action': 'POST',
                'effect': 'persistir',
                'evidence_class': 'controlled-ui-mock',
                'evidence_files': ['tests/test_flow.py'],
                'mutable_effect': True,
                'positive_control': True,
                'independent_read': '',
                'negative_control': False,
                'idempotency_applicable': True,
                'idempotency_verified': False,
            }]
        }
        codes = [item['code'] for item in audit.validate_journeys(repo, payload)]
        self.assertIn('JOURNEY_INDEPENDENT_READ_MISSING', codes)
        self.assertIn('JOURNEY_NEGATIVE_CONTROL_MISSING', codes)
        self.assertIn('JOURNEY_IDEMPOTENCY_MISSING', codes)

    def test_observabilidade_identifica_vinculos_de_execucao(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        file = repo / 'backend/app/api/runtime.py'
        file.write_text(
            "from fastapi import APIRouter\nrouter=APIRouter(prefix='/api/runtime')\n"
            "@router.get('/health')\ndef health():\n    correlation_id='corr'; environment='dev'; commit_sha='abc'; return {}\n",
            encoding='utf-8',
        )
        routes = audit.backend_routes(repo)
        obs = audit.observability_inventory(repo, routes)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]['category'], 'health')
        self.assertTrue(obs[0]['correlation_aware'])
        self.assertTrue(obs[0]['sha_aware'])
        self.assertTrue(obs[0]['environment_aware'])

    def test_inventario_de_referencias_lista_script_sem_consumidor(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / 'scripts').mkdir()
        (repo / 'docs').mkdir()
        (repo / 'scripts/orphan_tool.py').write_text('print(1)', encoding='utf-8')
        (repo / 'docs/used.md').write_text('# Usado', encoding='utf-8')
        (repo / 'frontend/src/views/HomeView.vue').write_text('<!-- docs/used.md -->', encoding='utf-8')
        inventory = audit.reference_inventory(repo)
        self.assertEqual(inventory['unreferenced_scripts'], [{'file': 'scripts/orphan_tool.py', 'references': 0}])
        self.assertFalse(any(item['file'] == 'docs/used.md' for item in inventory['unreferenced_docs']))


if __name__ == '__main__':
    unittest.main()
