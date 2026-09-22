import unittest

from scripts.build_empty_state_recovery_advisory import CARD_ID, build_advisory, publish_ops_dashboard


class EmptyStateRecoveryOpsDashboardTests(unittest.TestCase):
    def test_publishes_single_non_blocking_card(self):
        advisory = build_advisory({
            'contexts': {'analytics': 5},
            'recovery_by_context': {'analytics': 10},
        })
        dashboard = publish_ops_dashboard(
            {'cards': [{'id': CARD_ID, 'status': 'old'}, {'id': 'other'}]},
            advisory,
        )
        cards = [card for card in dashboard['cards'] if card.get('id') == CARD_ID]
        self.assertEqual(len(cards), 1)
        self.assertFalse(cards[0]['production_blocker'])
        self.assertEqual(cards[0]['mode'], 'advisory')
        self.assertEqual(cards[0]['priorities'][0]['priority'], 'P1')

    def test_safe_fallback_without_evidence(self):
        advisory = build_advisory({})
        self.assertFalse(advisory['evidence_complete'])
        self.assertEqual(advisory['priorities'], [])
        self.assertTrue(advisory['human_approval_required'])


if __name__ == '__main__':
    unittest.main()
