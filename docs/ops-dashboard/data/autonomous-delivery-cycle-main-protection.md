# Proteção de main — Autonomous Delivery Cycle

## Princípio

O ciclo só deve aumentar throughput se preservar `main` verde.

## Proteções

- Não processar PR sem CI verde.
- Não processar PR sem fila governada.
- Não processar PR sem autorização explícita.
- Observar CI pós-merge antes de iniciar novo incremento.
- Manter `max_prs=1` até maturidade comprovada.

## Pós-merge vermelho

Se qualquer run pós-merge concluir com falha:

1. parar novos incrementos;
2. remover labels de autorização de PRs pendentes;
3. corrigir `main`;
4. executar novo dry-run.
