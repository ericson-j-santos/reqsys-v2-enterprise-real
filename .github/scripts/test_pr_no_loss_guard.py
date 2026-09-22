import unittest

from pr_no_loss_guard import EXEMPT_LABEL, evaluate, parse_evidence


class ParseEvidenceTests(unittest.TestCase):
    def test_parseia_pr_substituta(self):
        result = parse_evidence('Motivo\n\nSubstituído por: #1400\n')
        self.assertEqual(result['replacement_pr'], 1400)
        self.assertIsNone(result['absorbed_commit'])

    def test_parseia_commit_absorvido(self):
        result = parse_evidence('Absorvido por commit: a1b2c3d4e5f6a7b8')
        self.assertEqual(result['absorbed_commit'], 'a1b2c3d4e5f6a7b8')
        self.assertIsNone(result['replacement_pr'])

    def test_sem_evidencia(self):
        result = parse_evidence('Fechado porque parece redundante.')
        self.assertIsNone(result['replacement_pr'])
        self.assertIsNone(result['absorbed_commit'])


class EvaluateTests(unittest.TestCase):
    def test_mergeado_e_permitido(self):
        allowed, reason = evaluate(
            {'number': 10, 'pull_request': {'number': 10, 'merged': True, 'labels': []}},
            'owner/repo',
        )
        self.assertTrue(allowed)
        self.assertIn('integrada', reason)

    def test_rotulo_verificado_e_permitido(self):
        allowed, reason = evaluate(
            {
                'number': 11,
                'pull_request': {
                    'number': 11,
                    'merged': False,
                    'labels': [{'name': EXEMPT_LABEL}],
                    'body': '',
                },
            },
            'owner/repo',
        )
        self.assertTrue(allowed)
        self.assertIn(EXEMPT_LABEL, reason)

    def test_fechada_sem_evidencia_e_bloqueada(self):
        allowed, reason = evaluate(
            {
                'number': 12,
                'pull_request': {
                    'number': 12,
                    'merged': False,
                    'labels': [],
                    'body': 'Sem referência de continuidade.',
                },
            },
            'owner/repo',
        )
        self.assertFalse(allowed)
        self.assertIn('não há prova', reason)


if __name__ == '__main__':
    unittest.main()
