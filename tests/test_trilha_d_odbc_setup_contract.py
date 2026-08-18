from pathlib import Path


WORKFLOW = Path(".github/workflows/trilha-d-qualidade-governanca.yml")
HELPER = Path(".github/scripts/install-unixodbc-ci.sh")


def test_odbc_setup_is_centralized_outside_workflow():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "apt-get update" not in workflow
    assert "apt-get install" not in workflow
    assert workflow.count("bash .github/scripts/install-unixodbc-ci.sh") == 2


def test_odbc_helper_has_bounded_retry_and_fail_closed_contract():
    helper = HELPER.read_text(encoding="utf-8")
    assert 'ATTEMPTS="${ODBC_APT_ATTEMPTS:-2}"' in helper
    assert 'TIMEOUT_SECONDS="${ODBC_APT_TIMEOUT_SECONDS:-45}"' in helper
    assert helper.count("timeout --preserve-status") == 2
    assert "dpkg-query" in helper
    assert "preservando fail-closed" in helper
    assert 'exit "${status}"' in helper
