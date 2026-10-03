# Delivery Maturity Snapshot

## Objetivo

Gerar um snapshot executivo, pesado e **report-only** da maturidade de entrega por dimensão, separando o estado atual evidenciado do estado alvo. O artifact não altera runtime produtivo, não promove deploy e não deve ser usado para declarar maturidade consolidada sem evidência anexada.

## Artifacts

| Artifact | Caminho | Uso |
| --- | --- | --- |
| JSON | `audit/delivery-maturity/delivery-maturity-snapshot.json` | Consumo automatizado, dashboard dinâmico e auditoria. |
| Markdown | `audit/delivery-maturity/delivery-maturity-snapshot.md` | Leitura executiva no Step Summary e evidência de PR. |
| Schema | `docs/contracts/delivery-maturity-snapshot.schema.json` | Contrato do payload publicado pelo workflow. |

## Dimensões mínimas

O snapshot publica as dimensões `técnico`, `operacional`, `usuário final`, `governança`, `produção`, `observabilidade`, `segurança` e `evidência`.

Cada dimensão contém:

- `current_percent`: percentual atual evidenciado.
- `target_percent`: percentual alvo desejado.
- `gap_percent`: diferença entre alvo e atual.
- `status_semáforo`: `verde`, `amarelo` ou `vermelho`.
- `confidence_level`: `low`, `medium` ou `high` conforme força da evidência.
- `evidence_links`: caminhos para artifacts, contratos, runbooks ou workflows usados como evidência.
- `next_recommended_action`: ação recomendada para reduzir gap ou elevar confiança.

## Política de interpretação

- `mode` deve permanecer `report_only` até decisão técnica formal.
- `runtime_impact` deve permanecer `none`; este incremento não altera runtime produtivo.
- Estado atual e estado alvo são campos separados e não devem ser tratados como equivalentes.
- Status `consolidado` não faz parte do contrato deste snapshot. O dashboard deve exibir semáforo e confiança, não consolidação.
- Confiança `low` força leitura conservadora mesmo quando o percentual atual parecer alto.

## Execução local

```bash
python scripts/delivery_maturity_snapshot.py
python -m json.tool audit/delivery-maturity/delivery-maturity-snapshot.json >/tmp/delivery-maturity-snapshot.pretty.json
```

## Workflow

O workflow **Delivery Maturity Snapshot** executa em `workflow_dispatch`, agenda periódica e alterações nos arquivos do próprio incremento. Ele publica o artifact `delivery-maturity-snapshot-${{ github.run_id }}` com JSON e Markdown.

## Dashboard dinâmico

O dashboard `docs/dashboard/live-operational-dashboard.dynamic.html` consome o JSON em `../audit/delivery-maturity/delivery-maturity-snapshot.json`, exibe cards executivos e uma tabela/drill-down com evidências e próxima ação por dimensão.

## Critérios de estabilização

1. JSON válido e aderente ao schema.
2. CI existente verde.
3. Evidências recentes anexadas ao PR.
4. PR mantido em draft até estabilização e validação operacional.
