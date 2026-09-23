# Extração de domínios e plataforma compartilhada de CI

## Objetivo

Reduzir o raio de impacto do CI do ReqSys sem criar fragmentação arbitrária.

A estratégia é **strangler**: o monorepo permanece autoritativo durante a transição,
cada domínio é inventariado e validado, o repositório alvo executa em paralelo e o
corte só ocorre após equivalência comprovada.

## Baseline

O inventário canônico está em `config/repository-domain-routing.json`.

No baseline `e41076b611450f2e49d5e9988045e65cb91a17fe`:

- workflows ativos em `.github/workflows`: **575**;
- workflows BACEN inventariados: **65**;
- nenhuma remoção de workflow BACEN é permitida nesta etapa;
- qualquer mudança na quantidade de workflows ativos exige atualização explícita do inventário.

## Topologia alvo

| Domínio | Repositório alvo | Estado inicial |
| --- | --- | --- |
| Core ReqSys | `ericson-j-santos/reqsys-v2-enterprise-real` | manter |
| CI compartilhado | `ericson-j-santos/reqsys-ci-platform` | preparado |
| BACEN | `ericson-j-santos/reqsys-governance-bacen` | preparado para shadow copy |
| Microsoft 365 | `ericson-j-santos/reqsys-integrations-m365` | planejado |
| Runtime/Operação | `ericson-j-santos/reqsys-runtime-platform` | planejado |
| Product Intelligence | `ericson-j-santos/reqsys-product-intelligence` | planejado |

## Primeira extração: BACEN

O manifesto BACEN contém os nomes exatos dos 65 workflows atuais.
O validador falha se um workflow `bacen-*.yml` for adicionado/removido sem atualização
do manifesto.

A ordem de corte é:

1. criar o repositório alvo com branch padrão protegida;
2. copiar o conteúdo BACEN pelo manifesto, preservando histórico quando tecnicamente viável;
3. executar CI no alvo em modo paralelo, sem desligar o source;
4. comparar inventário, contratos de evidência, resultados e artefatos;
5. somente após equivalência verde, mudar a autoridade para o alvo;
6. remover/delegar os workflows da origem em PR separado, com rollback documentado.

## Guardrails

- Required gates do Core não podem ser transferidos por acidente.
- Segredos nunca fazem parte do manifesto ou do histórico de extração.
- O target não se torna autoritativo por existir; precisa de equivalência evidenciada.
- Adição de novos workflows ativos exige atualização consciente do baseline.
- A migração não cria novo workflow de validação: o gate é incorporado ao
  `Path-Based Workflow Router Validation` já existente.

## Validação

```bash
python -m pytest tests/test_repository_domain_routing.py -q
python scripts/validate_repository_domain_routing.py --json
```

Resultado esperado: `status=passed`, contagem global igual ao baseline e inventário
BACEN sem drift.
