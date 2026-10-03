from app.services.vba_legacy_analyzer import analyze_vba_source


VBA_COMPLEXO = '''Attribute VB_Name = "modPedidos"
Option Explicit

Public Sub ProcessarPedido(ByVal Valor As Currency)
    On Error Resume Next
    Set cn = CreateObject("ADODB.Connection")
    cn.ConnectionString = "Server=sql01;Database=ERP;User ID=reqsys;Password=segredo"
    If Valor > 100000 Then
        Status = "APROVACAO"
    End If
    Call EnviarEmail
End Sub

Private Sub EnviarEmail()
    Set app = CreateObject("Outlook.Application")
End Sub
'''


def test_extrai_estrutura_regra_fluxo_e_candidato_de_requisito():
    resultado = analyze_vba_source(VBA_COMPLEXO, file_name='modPedidos.bas')

    assert resultado['execution_performed'] is False
    assert resultado['automatic_incorporation'] is False
    assert resultado['status'] == 'AGUARDANDO_REVISAO_HUMANA'
    assert resultado['module']['name'] == 'modPedidos'
    assert resultado['module']['option_explicit'] is True
    assert resultado['summary']['procedures'] == 2
    assert resultado['summary']['business_rules'] == 1
    assert resultado['procedures'][0]['calls'] == ['EnviarEmail']
    assert resultado['business_rules'][0]['expression'] == 'Valor > 100000'
    assert resultado['requirement_candidates'][0]['requires_human_validation'] is True
    assert 'Status = "APROVACAO"' in resultado['requirement_candidates'][0]['statement']


def test_mascara_segredo_e_classifica_riscos_sem_executar_codigo():
    resultado = analyze_vba_source(VBA_COMPLEXO, file_name='modPedidos.bas')

    riscos = {item['code']: item for item in resultado['risks']}
    assert riscos['VBA004']['severity'] == 'critical'
    assert 'segredo' not in riscos['VBA004']['evidence']
    assert '<redacted>' in riscos['VBA004']['evidence']
    assert riscos['VBA001']['severity'] == 'high'
    assert resultado['summary']['risks_by_severity']['critical'] == 1


def test_detecta_dependencias_excel_com_sql_arquivo_e_com():
    source = r'''Attribute VB_Name = "modIntegracao"
Sub Executar()
    Set ws = Worksheets("Entrada")
    arquivo = "\\servidor\financeiro\entrada.csv"
    Set cn = New ADODB.Connection
    sql = "SELECT id FROM pedidos WHERE status = 'PENDENTE'"
    Set fso = CreateObject("Scripting.FileSystemObject")
End Sub
'''

    resultado = analyze_vba_source(source, file_name='modIntegracao.bas')
    tipos = {item['type'] for item in resultado['dependencies']}

    assert {'worksheet', 'filesystem_path', 'database', 'sql', 'com_automation'} <= tipos
    assert any(item['name'] == 'Entrada' for item in resultado['dependencies'])
    assert any(item['name'] == 'ADODB' for item in resultado['dependencies'])


def test_sha_e_deterministico_para_quebras_de_linha_equivalentes():
    unix = 'Sub X()\nIf A = 1 Then B = 2\nEnd Sub\n'
    windows = unix.replace('\n', '\r\n')

    a = analyze_vba_source(unix, file_name='a.bas')
    b = analyze_vba_source(windows, file_name='a.bas')

    assert a['sha256'] == b['sha256']
    assert a['requirement_candidates'] == b['requirement_candidates']


def test_property_e_modulo_sem_end_sao_tolerados_sem_falha():
    source = '''Attribute VB_Name = "Cliente"
Private Property Get Nome() As String
    Nome = mNome
End Property
Public Function Incompleta(ByVal id As Long) As Boolean
    If id > 0 Then Incompleta = True
'''

    resultado = analyze_vba_source(source, file_name='Cliente.cls')

    assert resultado['module']['kind'] == 'class_module'
    assert [item['name'] for item in resultado['procedures']] == ['Nome', 'Incompleta']
    assert resultado['summary']['business_rules'] == 1
