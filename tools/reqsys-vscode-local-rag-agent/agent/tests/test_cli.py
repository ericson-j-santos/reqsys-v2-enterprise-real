from reqsys_agent.cli import main


def test_health_command():
    assert main(['health']) == 0


def test_governance_command(tmp_path):
    assert main(['governance', '--workspace', str(tmp_path)]) == 0
