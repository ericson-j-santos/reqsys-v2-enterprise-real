from scripts.build_executive_trend_history import build_history, build_snapshot


def test_build_snapshot_and_history():
    runtime = {
        'summary': {'executive_score': 82},
        'cards': {
            'readiness': {'readiness_percent': 84},
            'merge_intelligence': {'mergeability_score': 88},
        },
    }
    governance = {
        'summary': {
            'strategic_score': 90,
            'next_bottleneck': 'priorizacao_estrategica_e_consolidacao',
            'recommended_action': 'executar_agora',
        }
    }

    snapshot = build_snapshot(runtime, governance)
    history = build_history([], snapshot)

    assert snapshot['freeze_recommendation'] == 'safe_to_expand'
    assert history['summary']['executive_trend'] == 'stable'
    assert history['summary']['latest_next_bottleneck'] == 'priorizacao_estrategica_e_consolidacao'
    assert 'governed_expansion_only' in history['guardrails']
