from app.services.vba_call_graph import (
    analyze_vba_with_call_graph,
    attach_project_call_graph,
)


def test_call_explicita_liga_argumento_ao_parametro():
    source = '''
Attribute VB_Name = "modPedidos"
Sub Principal()
    total = Range("A1").Value
    Call Processar(total)
End Sub

Sub Processar(ByVal valor As Double)
    Range("B1").Value = valor * 2
End Sub
'''.strip()

    result = analyze_vba_with_call_graph(source, file_name='modPedidos.bas')

    graph = result['call_graph']
    assert graph['summary']['resolved_edges'] == 1
    edge = graph['edges'][0]
    assert edge['from'] == 'modPedidos.Principal'
    assert edge['to'] == 'modPedidos.Processar'
    assert edge['call_type'] == 'call_statement'
    assert edge['parameter_bindings'][0]['parameter'] == 'valor'
    assert edge['parameter_bindings'][0]['source_references'] == ['total']
    assert result['execution_performed'] is False


def test_application_run_literal_e_resolvido_sem_executar_macro():
    source = '''
Sub Principal()
    Application.Run "Enviar", total
End Sub

Sub Enviar(ByVal valor As Double)
End Sub
'''.strip()

    result = analyze_vba_with_call_graph(source, file_name='modRun.bas')

    edge = result['call_graph']['edges'][0]
    assert edge['call_type'] == 'application_run_literal'
    assert edge['to'] == 'modRun.Enviar'
    assert result['call_graph']['dynamic_or_unresolved_calls'] == []
    assert result['call_graph']['execution_performed'] is False


def test_application_run_dinamico_e_marcado_para_revisao_sem_vazar_literal():
    source = '''
Sub Principal()
    macroName = "SegredoInterno"
    Application.Run macroName, "Password=abc123"
End Sub
'''.strip()

    result = analyze_vba_with_call_graph(source, file_name='modDinamico.bas')

    calls = result['call_graph']['dynamic_or_unresolved_calls']
    assert len(calls) == 1
    assert calls[0]['status'] == 'DYNAMIC_TARGET'
    assert calls[0]['requires_human_review'] is True
    serialized = str(calls[0])
    assert 'abc123' not in serialized
    assert 'SegredoInterno' not in serialized


def test_recursao_indireta_gera_ciclo_rastreavel():
    source = '''
Sub A()
    Call B()
End Sub

Sub B()
    Call A()
End Sub
'''.strip()

    result = analyze_vba_with_call_graph(source, file_name='modCiclo.bas')

    assert result['call_graph']['summary']['resolved_edges'] == 2
    assert result['call_graph']['summary']['cycles'] == 1
    cycle = result['call_graph']['cycles'][0]
    assert cycle[0] == cycle[-1]
    assert set(cycle[:-1]) == {'modCiclo.A', 'modCiclo.B'}


def test_projeto_office_resolve_chamada_entre_modulos():
    analysis = {
        'summary': {'modules': 2},
        'modules': [
            {
                'name': 'modEntrada.bas',
                'procedures': [
                    {'name': 'Principal', 'calls': ['Persistir']},
                ],
            },
            {
                'name': 'modBanco.bas',
                'procedures': [
                    {'name': 'Persistir', 'calls': []},
                ],
            },
        ],
    }

    result = attach_project_call_graph(analysis)

    assert result['call_graph']['scope'] == 'office_project'
    assert result['call_graph']['summary']['resolved_edges'] == 1
    assert result['call_graph']['edges'][0]['from'] == 'modEntrada.bas.Principal'
    assert result['call_graph']['edges'][0]['to'] == 'modBanco.bas.Persistir'


def test_projeto_office_nao_inventa_destino_quando_nome_e_ambiguo():
    analysis = {
        'summary': {'modules': 3},
        'modules': [
            {
                'name': 'modEntrada.bas',
                'procedures': [{'name': 'Principal', 'calls': ['Executar']}],
            },
            {
                'name': 'modA.bas',
                'procedures': [{'name': 'Executar', 'calls': []}],
            },
            {
                'name': 'modB.bas',
                'procedures': [{'name': 'Executar', 'calls': []}],
            },
        ],
    }

    result = attach_project_call_graph(analysis)

    assert result['call_graph']['summary']['resolved_edges'] == 0
    unresolved = result['call_graph']['dynamic_or_unresolved_calls'][0]
    assert unresolved['status'] == 'AMBIGUOUS_TARGET'
    assert unresolved['requires_human_review'] is True
