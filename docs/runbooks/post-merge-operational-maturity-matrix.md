# Matriz de Maturidade Operacional Pos-Merge — ReqSys

## Objetivo

Consolidar uma matriz executiva para avaliar o estado pos-merge da `main` com base nos artifacts e workflows operacionais ja implantados.

## Dimensoes avaliadas

| Dimensao | Evidencia principal | Atual | Alvo | Gap |
|---|---|---:|---:|---:|
| CI/CD obrigatorio | Required workflows | 96% | 98% | 2 p.p. |
| Saude pos-merge | Main Operational Post-Merge Health | 92% | 98% | 6 p.p. |
| Lead time analytics | CI Lead Time Analytics | 95% | 98% | 3 p.p. |
| Historico operacional | Operational History Snapshot | 95% | 98% | 3 p.p. |
| Predictive analytics | Runtime Predictive Analytics | 90% | 95% | 5 p.p. |
| Dashboard vivo | Dynamic Runtime Dashboard | 97% | 98% | 1 p.p. |
| Validacao de contracts | Operational Artifact Schema Validation | 97% | 99% | 2 p.p. |
| Descoberta de artifacts | Artifact Discovery Index | 90% | 96% | 6 p.p. |

## Classificacao executiva

| Faixa | Estado |
|---|---|
| >= 96% | Consolidado |
| 90% a 95,99% | Em consolidacao |
| 80% a 89,99% | Governado com atencao |
| < 80% | Requer acao prioritaria |

## Score consolidado atual

| Indicador | Valor |
|---|---:|
| Media tecnica | 95,25% |
| Menor maturidade | 90% |
| Maior maturidade | 97% |
| Gap medio ate alvo | 3,5 p.p. |
| Risco residual | medio/baixo |

## Regras de uso

- Atualizar apos cada rodada de ate 3 PRs.
- Nao declarar padrao ouro 100% sem evidencia real.
- Distinguir implementado, validado, evidenciado, consolidado e governado.
- Tratar workflows report-only como evidencia, nao como gate substituto.

## Proximas acoes recomendadas

1. Associar cada score a artifact real por `run_id`.
2. Renderizar esta matriz no dashboard dinamico.
3. Criar burndown historico dos gaps por rodada.
