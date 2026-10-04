# Operational Governance Dashboard

## Objetivo

Gerar um dashboard HTML executivo a partir do artifact JSON do `Operational Governance Orchestrator`.

## Entrada

Arquivo esperado:

`artifacts/operational-governance-orchestrator/operational-governance-orchestrator.json`

## Saída

Arquivo gerado:

`artifacts/operational-governance-orchestrator/dashboard.html`

O HTML é incluído no artifact:

`operational-governance-orchestrator-evidence`

## Conteúdo do dashboard

- score operacional;
- estado consolidado;
- decisão operacional;
- runs críticos;
- falhas críticas;
- pendências;
- PRs abertos;
- workflows críticos ausentes na janela;
- links diretos para runs e PRs.

## Guard rails

O dashboard não:

- executa rerun;
- faz merge;
- faz deploy;
- altera produção;
- altera secrets;
- altera branch protection;
- altera labels.

## Uso operacional

1. Executar o workflow `Operational Governance Orchestrator`.
2. Baixar o artifact `operational-governance-orchestrator-evidence`.
3. Abrir `dashboard.html` localmente.
4. Validar estado, score, pendências e links.

## Critério de aceite

| Critério | Estado alvo |
|---|---|
| Artifact publicado | Sim |
| `dashboard.html` presente | Sim |
| JSON fonte presente | Sim |
| `summary.md` presente | Sim |
| Links clicáveis | Sim |
| Layout responsivo | Sim |
| Sem dependência externa/CDN | Sim |
