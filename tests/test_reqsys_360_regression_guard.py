import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'reqsys_360_regression_guard.py'
spec = spec_from_file_location('reqsys_360_regression_guard', MODULE_PATH)
guard = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(guard)


class ReqSys360RegressionGuardTests(unittest.TestCase):
    def test_aprova_valores_dentro_do_baseline(self):
        baseline = {
            'version': 1,
            'frontend': {'critical': {'max': 0}, 'hygiene_markers': {'max': 0}},
            'repository': {'critical': {'max': 0}, 'journey_contract_violations': {'max': 0}},
        }
        result = guard.build_result(
            baseline,
            {'summary': {'critical': 0, 'hygiene_markers': 0}},
            {'summary': {'critical': 0, 'journey_contract_violations': 0}},
        )
        self.assertEqual(result['status'], 'approved')
        self.assertEqual(result['violations'], [])

    def test_bloqueia_regressao_acima_do_maximo(self):
        violations = guard.evaluate({'critical': 1}, {'critical': {'max': 0}}, 'frontend')
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]['code'], 'BASELINE_MAX_EXCEEDED')

    def test_bloqueia_desaparecimento_de_metrica_governada(self):
        violations = guard.evaluate({}, {'critical': {'max': 0}}, 'frontend')
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]['code'], 'BASELINE_METRIC_MISSING')


if __name__ == '__main__':
    unittest.main()
