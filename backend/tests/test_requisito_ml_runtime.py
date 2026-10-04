from app.services import requisito_ml_runtime as runtime


def setup_function():
    runtime.limpar_cache_runtime()


def teardown_function():
    runtime.limpar_cache_runtime()


def test_runtime_off_nao_carrega_modelo(monkeypatch):
    monkeypatch.setenv('REQSYS_ML_REQUISITOS_MODO', 'off')

    def falhar():
        raise AssertionError('contexto não deveria ser carregado em off')

    monkeypatch.setattr(runtime, '_carregar_contexto', falhar)
    assert runtime.avaliar_requisito_observacional('texto', correlation_id='corr-off') is None


def test_runtime_shadow_calcula_modelo_sem_alterar_baseline(monkeypatch):
    monkeypatch.setenv('REQSYS_ML_REQUISITOS_MODO', 'shadow')
    decisao = runtime.avaliar_requisito_observacional(
        'O serviço deve integrar eventos com uma API externa.',
        correlation_id='corr-shadow',
    )
    assert decisao is not None
    assert decisao.modo == 'shadow'
    assert decisao.categoria == decisao.baseline_categoria
    assert decisao.modelo_categoria is not None
    assert decisao.fallback_reason == 'SHADOW_ONLY'


def test_runtime_shadow_contabiliza_aprovacoes_humanas_reais(monkeypatch):
    monkeypatch.setenv('REQSYS_ML_REQUISITOS_MODO', 'shadow')
    contexto = runtime._carregar_contexto()
    assert contexto.amostras_aprovadas == 16
    assert contexto.modelo.exportar_estado()['total_documentos'] == 72


def test_runtime_nao_permite_canary_por_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv('REQSYS_ML_REQUISITOS_MODO', 'canary')
    assert runtime.avaliar_requisito_observacional('texto', correlation_id='corr-canary') is None


def test_runtime_nao_permite_active_por_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv('REQSYS_ML_REQUISITOS_MODO', 'active')
    assert runtime.avaliar_requisito_observacional('texto', correlation_id='corr-active') is None


def test_runtime_configuracao_invalida_falha_seguro(monkeypatch):
    monkeypatch.setenv('REQSYS_ML_REQUISITOS_MODO', 'modo-invalido')
    assert runtime.avaliar_requisito_observacional('texto', correlation_id='corr-invalid') is None


def test_runtime_indisponivel_nao_interrompe_fluxo(monkeypatch):
    monkeypatch.setenv('REQSYS_ML_REQUISITOS_MODO', 'shadow')

    def falhar():
        raise RuntimeError('falha controlada')

    monkeypatch.setattr(runtime, '_carregar_contexto', falhar)
    assert runtime.avaliar_requisito_observacional('texto', correlation_id='corr-error') is None
