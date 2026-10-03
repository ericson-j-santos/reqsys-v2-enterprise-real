import pytest

from scripts.select_integration_excel_sql_sharepoint_real_candidate import choose_real_candidate


def test_choose_real_candidate_rejeita_fixture_e_residuo_sharepoint():
    selected, stats = choose_real_candidate(
        ["990000000000001", "111", "222"],
        [{"id": "1", "fields": {"ChaveIntegracao": "111"}}],
    )

    assert selected == "222"
    assert stats == {
        "candidate_count": 3,
        "synthetic_rejected_count": 1,
        "sharepoint_residue_rejected_count": 1,
        "eligible_count": 1,
    }


def test_choose_real_candidate_falha_sem_candidato_elegivel():
    with pytest.raises(RuntimeError, match="nenhum_identificador_real_elegivel_no_excel"):
        choose_real_candidate(
            ["990000000000001", "111"],
            [{"id": "1", "fields": {"ChaveIntegracao": "111"}}],
        )
