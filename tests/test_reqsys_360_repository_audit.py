import json
import tempfile
import unittest
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

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
            ]
        }
        self.assertEqual(audit.validate_governance(valid), [])
        invalid = {'routes': valid['routes'] + [valid['routes'][1]]}
        codes = [item['code'] for item in audit.validate_governance(invalid)]
        self.assertIn('GOVERNANCE_ROUTE_DUPLICATE', codes)

    def test_estado_de_ui_e_candidato_de_servico_sao_inventario_nao_bloqueante(self):
        temp, repo = self.make_repo()
        self.addCleanup(temp.cleanup)
        (repo / 'frontend/src/router/index.js').write_text(
            "import HomeView from '../views/HomeView.vue'\nexport const routes = [\n  { path: '/', component: HomeView }\n]\n",
            encoding='utf-8',
        )
        (repo / 'frontend/src/views/HomeView.vue').write_text('<template>Sem dados</template>', encoding='utf-8')
        (repo / 'frontend/src/services/orphan.js').write_text('export const x = 1', encoding='utf-8')
        (repo / 'governance/reqsys-360/route-responsibilities.json').write_text(
            json.dumps({'routes': [{'route': '/', 'area': 'trabalho', 'status': 'canonical', 'responsibility': 'Painel'}]}),
            encoding='utf-8',
        )
        report = audit.generate_report(repo)
        self.assertEqual(report['summary']['critical'], 0)
        self.assertEqual(report['summary']['ui_routes'], 1)
        self.assertEqual(report['summary']['service_orphan_candidates'], 1)
        self.assertTrue(any(item['code'] == 'UI_STATE_COVERAGE_LOW' for item in report['findings']))


if __name__ == '__main__':
    unittest.main()
