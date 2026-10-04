# Storage Histórico Governado — ReqSys

## Objetivo

Definir a camada governada de armazenamento histórico dos snapshots operacionais do ReqSys, preservando rastreabilidade, retenção, baixo risco e separação entre artifact temporário e storage de longo prazo.

## Estratégia padrão ouro

| Camada | Função | Estado |
|---|---|---|
| Artifact GitHub Actions | evidência temporária | ativo |
| Índice histórico | catálogo de snapshots | introduzido |
| Storage governado | persistência longa | alvo controlado |
| Dashboard dinâmico | consumo visual | ativo |
| Predictive analytics | consumo analítico | alvo |

## Política de retenção

| Item | Política |
|---|---|
| Artifacts de workflow | 30 dias |
| Índice lógico | versionado no repositório |
| Storage longo prazo | somente após decisão governada |
| Dados sensíveis | proibidos |
| Secrets | proibidos |

## Contrato

O índice deve seguir o schema:

- `docs/contracts/operational-history-index.schema.json`

## Maturidade atual

| Indicador | Atual | Alvo | Gap |
|---|---:|---:|---:|
| Histórico via artifacts | 89% | 95% | 6 p.p. |
| Índice governado | 50% | 95% | 45 p.p. |
| Retenção longa | 40% | 90% | 50 p.p. |
| Consumo por dashboard | 70% | 95% | 25 p.p. |

## Limites

- Não escrever automaticamente no repositório em cada execução sem política aprovada.
- Não persistir payloads sensíveis.
- Não transformar monitor report-only em gate bloqueante.
- Não depender de storage externo sem aprovação de segurança/custo.

## Próxima evolução

Criar workflow que publique um índice JSON report-only e, depois, avaliar armazenamento longo em branch dedicada ou storage externo governado.
