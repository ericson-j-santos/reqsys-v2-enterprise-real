from pathlib import Path

import pytest
from defusedxml.common import DefusedXmlException

from app.services.movimento_email.ssrs_discovery import descobrir_origem_ssrs


def test_descobre_servidor_banco_objetos_sem_expor_credenciais(tmp_path: Path):
    rdl = tmp_path / 'Movimento.rdl'
    rdl.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition">
  <DataSources>
    <DataSource Name="MovimentoDS">
      <ConnectionProperties>
        <DataProvider>SQL</DataProvider>
        <ConnectString>Data Source=sql-prod-01;Initial Catalog=Movimento;User ID=svc;Password=nao-vazar</ConnectString>
        <IntegratedSecurity>false</IntegratedSecurity>
      </ConnectionProperties>
    </DataSource>
  </DataSources>
  <DataSets>
    <DataSet Name="Resumo">
      <Query>
        <DataSourceName>MovimentoDS</DataSourceName>
        <CommandText>SELECT a.Id FROM dbo.Movimento a JOIN dbo.Cliente c ON c.Id=a.ClienteId</CommandText>
      </Query>
    </DataSet>
  </DataSets>
</Report>''',
        encoding='utf-8',
    )

    resultado = descobrir_origem_ssrs(tmp_path)

    assert resultado['servidores'] == ['sql-prod-01']
    assert resultado['bancos'] == ['Movimento']
    assert resultado['objetos_sql_candidatos'] == ['dbo.Cliente', 'dbo.Movimento']
    assert 'UID=' not in resultado['dsn_molde_sem_credenciais']
    assert 'Password=' not in resultado['dsn_molde_sem_credenciais']
    assert 'nao-vazar' not in str(resultado)
    assert resultado['credencial_exposta_no_resultado'] is False
    assert resultado['detalhes'][0]['fontes'][0]['credencial_embutida_detectada'] is True


def test_reporta_data_source_compartilhado_pendente(tmp_path: Path):
    rdl = tmp_path / 'Movimento.rdl'
    rdl.write_text(
        '''<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition">
  <DataSources>
    <DataSource Name="MovimentoDS"><DataSourceReference>/Dados/Movimento</DataSourceReference></DataSource>
  </DataSources>
</Report>''',
        encoding='utf-8',
    )

    resultado = descobrir_origem_ssrs(rdl)

    assert resultado['data_sources_compartilhados_pendentes'] == ['/Dados/Movimento']
    assert resultado['dsn_molde_sem_credenciais'] is None


def test_rejeita_xml_ssrs_com_entidade_externa(tmp_path: Path):
    rdl = tmp_path / 'MovimentoMalicioso.rdl'
    rdl.write_text(
        '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE Report [
  <!ENTITY arquivo SYSTEM "file:///etc/passwd">
]>
<Report xmlns="http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition">
  <DataSources>&arquivo;</DataSources>
</Report>''',
        encoding='utf-8',
    )

    with pytest.raises(DefusedXmlException):
        descobrir_origem_ssrs(rdl)
