from app.services.teams_graph_identity import TeamsGraphIdentity
from datetime import datetime, timezone


def test_evidence_nao_expoe_secret_ou_token():
    identity = TeamsGraphIdentity(
        profile_name='reqsys-test-teams',
        environment='test',
        tenant_id='tenant-id',
        client_id='client-id-12345678',
        client_secret='segredo-que-nao-pode-vazar',
        rotation_due_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        rotation_required=False,
    )

    evidence = identity.evidence()
    serialized = str(evidence).lower()

    assert 'client_secret' not in evidence
    assert 'segredo-que-nao-pode-vazar' not in serialized
    assert 'token' not in serialized
    assert evidence['client_id_suffix'] == '12345678'
