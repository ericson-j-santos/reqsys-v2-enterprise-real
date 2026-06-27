# Validação regressiva do dashboard operacional dinâmico

## Objetivo

Este runbook descreve a validação estática, pesada e segura, usada para evitar regressões no dashboard operacional dinâmico em `docs/dashboard/` sem redesenhar a experiência, trocar stack ou remover cards existentes.

## Escopo validado

O comando canônico é:

```bash
npm run validate:dashboard-regression
```

A validação executa `scripts/validate-dashboard-regression.mjs` e gera evidências em:

- `docs/dashboard/dashboard-regression-report.json`
- `docs/dashboard/dashboard-regression-report.md`

## Gates report-only

A primeira versão é intencionalmente **report-only**. O script sempre retorna sucesso operacional quando consegue executar e gerar os relatórios, mesmo que encontre gaps. Isso permite manter CI verde enquanto os gaps iniciais são tratados como backlog governado.

Os checks cobrem:

| Check | Critério |
| --- | --- |
| Dashboards HTML identificados | Deve existir pelo menos um `.html` em `docs/dashboard/`. |
| Cards obrigatórios | O dashboard dinâmico deve preservar os cards operacionais esperados. |
| Fontes JSON esperadas | As fontes `../audit/**/*.json` consumidas pelo dashboard devem continuar referenciadas. |
| Fallback seguro | O dashboard deve manter `loadJson`, `try/catch`, `response.ok` e uso de `fallback[source.key]`. |
| Ausência de secrets | Padrões comuns de token, chave privada, JWT e credenciais inline são reportados como gaps. |
| Chamadas externas não governadas | URLs `http(s)`, CDN, scripts remotos, links remotos e imports remotos são reportados como gaps. |
| Execução local básica | Cada HTML deve manter `doctype`, `lang="pt-BR"` e viewport para abertura local simples. |
| Evidence Hub cards executivos | `operational-evidence-hub.html` deve preservar cards de consolidação dos 8 domínios. |
| Evidence Hub fontes JSON | O hub deve referenciar artifacts de readiness, completion, finalization, maturidade, observabilidade, contratos, regressão e rastreabilidade. |
| Evidence Hub drill-down | Seções navegáveis por âncora para cada domínio consolidado. |
| Evidence Hub fallback | Mesmo padrão de `loadJson` + `fallback[domain.key]` do dashboard dinâmico. |

## Como interpretar o relatório

- `status: passed`: critério preservado.
- `status: gap`: achado report-only que deve ser avaliado antes de promover para gate bloqueante.
- `severity: report-only`: achado não bloqueia CI nesta versão.

O arquivo Markdown é a evidência humana para PRs e auditorias. O JSON é a evidência estruturada para automações futuras.

## Procedimento para PR

1. Execute `npm run validate:dashboard-regression`.
2. Revise `docs/dashboard/dashboard-regression-report.md`.
3. Anexe no PR o resumo de checks, quantidade de gaps e link/caminho dos relatórios.
4. Se houver gap real de segurança, corrija antes de merge ou registre decisão técnica explícita.
5. Não remova cards existentes para fazer o relatório passar; ajuste o contrato de validação somente com justificativa rastreável.

## Evolução futura

Quando o histórico de gaps estabilizar, promover gradualmente checks críticos para modo bloqueante, começando por secrets e chamadas externas não governadas.
