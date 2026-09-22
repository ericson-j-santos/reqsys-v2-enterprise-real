def test_deve_salvar_e_listar_resultado(repository_tmp, resultado_verde):
    repository_tmp.salvar(resultado_verde)

    registros = repository_tmp.listar_ultimos()

    assert len(registros) == 1
    assert registros[0]["nome"] == "api_teste"
    assert registros[0]["status_operacional"] == "VERDE"
