# Decision Log — Aba Estatísticas v1

| Data | Decisão | Justificativa |
|---|---|---|
| 2026-06-21 | Criar aba própria `/estatisticas` | Separar analytics da solução de monitoramento operacional geral |
| 2026-06-21 | Começar internal-first | Reduz risco de usar fontes externas sem governança |
| 2026-06-21 | Externo inicial como `nao_medido` | Evita falsa maturidade e dados não auditados |
| 2026-06-21 | Exigir fonte e fórmula | Garante rastreabilidade mínima |
| 2026-06-21 | Manter PR em draft | CI/build ainda precisam validar execução |

## Decisão atual recomendada

Prosseguir para PR draft e aguardar CI. Corrigir qualquer falha antes de conectar novas fontes.
