# Rastreabilidade VBA / Excel / SQL

A análise é estática: não executa Office/VBA e não persiste a fonte.

| Etapa | Evidência | Exemplo sanitizado | Critério |
| --- | --- | --- | --- |
| Entrada | procedimento/parâmetro | Processar(codigo) | preservar contrato de entrada |
| Célula | excel_input | Entrada!B2 | identificar origem |
| Transformação | assigns_or_transforms | entrada para status | manter linhagem |
| Regra | business_rules | condição de status | gerar candidato com validação humana |
| SQL | database_sink | consulta parametrizada | identificar destino sem executar |
| Excel | excel_output | Saida!C5 | identificar célula de destino |
| Arquivo | file_sink | resultado.txt | identificar gravação |
| Mensagem | message_sink | envio | identificar efeito externo |
| Teste | test_candidates | Given/When/Then | requires_human_validation=true |

Formatos de fonte: .bas, .cls, .frm, .vba e .txt. Contêineres Office seguem a extração governada descrita em VBA_LEGACY_ANALYZER.md.
