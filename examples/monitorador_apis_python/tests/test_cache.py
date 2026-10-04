import time


def test_deve_salvar_e_obter_item_do_cache(cache_curto):
    cache_curto.salvar("chave", {"valor": 123})

    assert cache_curto.obter("chave") == {"valor": 123}


def test_deve_expirar_item_do_cache(cache_curto):
    cache_curto.salvar("chave", "valor")

    time.sleep(1.1)

    assert cache_curto.obter("chave") is None
