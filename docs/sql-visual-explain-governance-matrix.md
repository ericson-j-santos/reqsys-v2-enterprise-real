# Matriz de Governança — SQL Visual Explain Stack

| Dimensão | Regra | Evidência esperada |
|---|---|---|
| Rastreabilidade | Toda query relevante deve ter objetivo | Markdown versionado |
| Segurança | Nenhum segredo ou PII em exemplos | Revisão + CI futuro |
| Performance | Query crítica deve ter plano analisado | EXPLAIN documentado |
| Arquitetura viva | Relações devem ter diagrama | Mermaid/ERD |
| Qualidade | Parser deve ter teste | Pytest |
| Operação | Runbook deve existir | Documento versionado |
| Maturidade | Status deve refletir evidência | Status documentado |
