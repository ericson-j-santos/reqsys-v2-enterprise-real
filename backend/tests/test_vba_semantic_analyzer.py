from app.services.vba_semantic_analyzer import analyze_vba_semantics


VBA_DATAFLOW = '''Attribute VB_Name = "modFechamento"
Option Explicit

Public Function CalcularTotal(ByVal taxa As Double) As Double
    valor = Worksheets("Entrada").Range("B2").Value
    total = valor * taxa
    If total > 1000 Then
        status = "APROVAR"
    End If
    Worksheets("Saida").Range("C5").Value = total
    CalcularTotal = total
End Function
'''


def test_mapeia_origem_transformacao_e_destino_excel():
    resultado = analyze_vba_semantics(VBA_DATAFLOW, file_name='modFechamento.bas')
    fluxo = resultado['semantic_analysis']['data_flow']

    assert resultado['execution_performed'] is False
    assert resultado['semantic_analysis']['source_persisted'] is False
    assert resultado['summary']['data_flow_edges'] >= 4
    assert any(node['type'] == 'excel_input' and node['name'] == 'Entrada!B2' for node in fluxo['nodes'])
    assert any(node['type'] == 'excel_output' and node['name'] == 'Saida!C5' for node in fluxo['nodes'])
    assert any(node['type'] == 'parameter' and node['name'] == 'CalcularTotal.taxa' for node in fluxo['nodes'])
    assert any(edge['procedure'] == 'CalcularTotal' for edge in fluxo['edges'])


def test_preserva_linhagem_ate_valor_de_retorno():
    resultado = analyze_vba_semantics(VBA_DATAFLOW, file_name='modFechamento.bas')
    fluxo = resultado['semantic_analysis']['data_flow']

    retorno = next(node for node in fluxo['nodes'] if node['type'] == 'return_value')
    arestas_retorno = [edge for edge in fluxo['edges'] if edge['to'] == retorno['id']]

    assert retorno['name'] == 'CalcularTotal'
    assert arestas_retorno
    assert any('excel_input:entrada-b2' == edge['from'] for edge in arestas_retorno)


def test_gera_candidatos_de_teste_para_regra_e_destino():
    resultado = analyze_vba_semantics(VBA_DATAFLOW, file_name='modFechamento.bas')
    candidatos = resultado['semantic_analysis']['test_candidates']

    assert any(item['type'] == 'business_rule' for item in candidatos)
    assert any(item['type'] == 'data_flow_sink' for item in candidatos)
    assert all(item['requires_human_validation'] is True for item in candidatos)
    assert resultado['summary']['test_candidates'] == len(candidatos)


def test_mapeia_sql_para_destino_de_banco_sem_executar():
    source = '''Attribute VB_Name = "modBanco"
Sub Persistir(ByVal id As Long)
    sql = "UPDATE pedidos SET status = 'OK' WHERE id = " & id
    cn.Execute sql
End Sub
'''

    resultado = analyze_vba_semantics(source, file_name='modBanco.bas')
    fluxo = resultado['semantic_analysis']['data_flow']

    assert any(node['type'] == 'sql_literal' for node in fluxo['nodes'])
    assert any(node['type'] == 'database_sink' for node in fluxo['nodes'])
    assert any(edge['relation'] == 'executes_sql' for edge in fluxo['edges'])
    assert resultado['execution_performed'] is False


def test_nao_expoe_valor_de_segredo_em_evidencia_semantica():
    source = '''Attribute VB_Name = "modConexao"
Sub X()
    conexao = "Server=x;Password=senha-ultrassecreta-123"
End Sub
'''

    resultado = analyze_vba_semantics(source, file_name='modConexao.bas')
    serializado = str(resultado['semantic_analysis'])

    assert 'senha-ultrassecreta-123' not in serializado
    assert '<redacted>' in serializado
