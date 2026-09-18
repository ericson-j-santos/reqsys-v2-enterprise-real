from scripts.trilha_d_coverage_dimension import parse_coverage_percent


def test_parse_coverage_percent_prioriza_linha_total_com_decimal():
    output = """
    Name                                  Stmts   Miss  Cover
    ---------------------------------------------------------
    app/api/exemplo.py                       10      7    30%
    app/services/exemplo.py                 100     25    75%
    ---------------------------------------------------------
    TOTAL                                  1072    276  74.29%
    Required test coverage of 60% reached. Total coverage: 74.29%
    """

    assert parse_coverage_percent(output) == 74.29


def test_parse_coverage_percent_nao_usa_percentual_intermediario():
    output = """
    app/api/exemplo.py                       10      7    29%
    app/services/exemplo.py                 100     25    75%
    TOTAL                                  1072    276  74%
    """

    assert parse_coverage_percent(output) == 74.0


def test_parse_coverage_percent_usa_total_coverage_como_fallback():
    output = "Required test coverage of 60% reached. Total coverage: 74.29%"

    assert parse_coverage_percent(output) == 74.29


def test_parse_coverage_percent_retorna_none_sem_cobertura_total():
    output = "29% em arquivo parcial, sem linha TOTAL e sem Total coverage"

    assert parse_coverage_percent(output) is None
