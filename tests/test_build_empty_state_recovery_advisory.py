import unittest

from scripts.build_empty_state_recovery_advisory import build_advisory


class EmptyStateRecoveryAdvisoryTests(unittest.TestCase):
    def test_orders_lowest_recovery_first(self):
        advisory = build_advisory({
            'contexts': {'dashboard-a': 5, 'dashboard-b': 2},
            'recovery_by_context': {'dashboard-a': 60, 'dashboard-b': 10},
        })
        self.assertEqual(advisory['priorities'][0]['context'], 'dashboard-b')
        self.assertEqual(advisory['priorities'][0]['priority'], 'P1')
        self.assertFalse(advisory['production_blocker'])

    def test_safe_empty_advisory(self):
        advisory = build_advisory({})
        self.assertEqual(advisory['priorities'], [])
        self.assertEqual(advisory['mode'], 'advisory')
        self.assertTrue(advisory['human_approval_required'])


if __name__ == '__main__':
    unittest.main()
