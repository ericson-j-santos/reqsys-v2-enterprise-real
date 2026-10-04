import json
import tempfile
import unittest
from pathlib import Path

from tools.operational_sync.operational_sync_engine import OperationalTask, build_snapshot, load_tasks


class OperationalSyncEngineTests(unittest.TestCase):
    def test_sem_input_nao_declara_evidencia_operacional(self):
        snapshot = build_snapshot([])

        self.assertEqual(snapshot['status'], 'evidence_required')
        self.assertFalse(snapshot['operational_evidence'])
        self.assertIsNone(snapshot['risk_average'])
        self.assertEqual(snapshot['tasks_total'], 0)

    def test_input_real_gera_score_limitado(self):
        task = OperationalTask(
            id='task-1',
            title='Falha governada',
            source='github',
            status='failure',
            impact=80,
            production_risk=90,
            recurrence=70,
            blocked_minutes=180,
            dependencies=50,
            urgency=90,
            evidence=['run_id=123', 'head_sha=abc'],
        )

        snapshot = build_snapshot([task], correlation_id='corr-test')

        self.assertTrue(snapshot['operational_evidence'])
        self.assertEqual(snapshot['correlation_id'], 'corr-test')
        self.assertGreaterEqual(snapshot['tasks'][0]['risk_score'], 0)
        self.assertLessEqual(snapshot['tasks'][0]['risk_score'], 100)

    def test_load_tasks_falha_fechado_com_contrato_incompleto(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.json'
            path.write_text(json.dumps([{'id': 'incompleto'}]), encoding='utf-8')
            with self.assertRaises(ValueError):
                load_tasks(str(path))


if __name__ == '__main__':
    unittest.main()
