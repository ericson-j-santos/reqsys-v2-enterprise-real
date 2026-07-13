import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.smoke_executive_final_sync_history_public_smoke_trend import smoke


class ExecutiveFinalSyncHistoryPublicSmokeTrendTests(unittest.TestCase):
    def test_passes_when_dashboard_and_contract_are_synchronized(self) -> None:
        html = '<section id="executive-final-sync-history-public-smoke-trend" data-mode="report-only" data-production-blocker="false"></section>'
        contract = json.dumps({
            'cards': {
                'executive_final_sync_history_public_smoke_trend': {
                    'status': 'eligible-for-human-review',
                    'environment_coverage': '3/3',
                    'samples': 9,
                    'pass_rate': 100,
                    'minimum_stable_sequence': 3,
                    'eligible_for_human_review': True,
                    'mode': 'report-only',
                    'production_blocker': False,
                    'human_approval_required': True,
                }
            }
        })
        with patch('scripts.smoke_executive_final_sync_history_public_smoke_trend.fetch_text', side_effect=[html, contract]):
            evidence = smoke('https://example.test', 'dev')
        self.assertEqual(evidence['status'], 'passed')
        self.assertEqual(evidence['decision'], 'SYNCHRONIZED')

    def test_blocks_when_contract_is_missing(self) -> None:
        html = '<section id="executive-final-sync-history-public-smoke-trend" data-mode="report-only" data-production-blocker="false"></section>'
        with patch('scripts.smoke_executive_final_sync_history_public_smoke_trend.fetch_text', side_effect=[html, '{}']):
            evidence = smoke('https://example.test', 'stg')
        self.assertEqual(evidence['status'], 'failed')
        self.assertIn('contract_card_present', evidence['errors'])

    def test_blocks_when_automatic_production_blocker_is_enabled(self) -> None:
        html = '<section id="executive-final-sync-history-public-smoke-trend" data-mode="report-only" data-production-blocker="false"></section>'
        contract = json.dumps({'cards': {'executive_final_sync_history_public_smoke_trend': {
            'mode': 'report-only', 'production_blocker': True, 'human_approval_required': True
        }}})
        with patch('scripts.smoke_executive_final_sync_history_public_smoke_trend.fetch_text', side_effect=[html, contract]):
            evidence = smoke('https://example.test', 'prod')
        self.assertIn('production_blocker_disabled', evidence['errors'])


if __name__ == '__main__':
    unittest.main()
