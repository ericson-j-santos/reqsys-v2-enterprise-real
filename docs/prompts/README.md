# Prompt Development Governance

Data de referência: 2026-07-20

## Objetivo

Organizar, versionar e coordenar prompts usados na análise, implementação, revisão, teste e entrega de código do ReqSys.

Esta estrutura complementa os ADRs:

- **ADR**: decisão arquitetural durável;
- **PDR — Prompt Development Record**: contrato operacional reutilizável para execução de uma classe de tarefa;
- **Execution Record**: evidência de uma execução concreta em issue, branch, commit, PR, workflow ou relatório.

## Fluxo obrigatório

```text
Solicitação
  → classificação de domínio e risco
  → ADRs aplicáveis
  → PDR aplicável
  → plano de execução
  → implementação por agente(s)
  → validações
  → evidências
  → PR/entrega
  → atualização do catálogo quando necessário
```

## Organização

```text
docs/prompts/
├── README.md
├── catalog.md
├── templates/
│   └── PDR-TEMPLATE.md
├── development/
├── review/
├── ci-cd/
├── security/
└── operations/
```

## Convenção de identificação

Formato:

```text
PDR-<DOMINIO>-<NNN>-<titulo-kebab-case>.md
```

Domínios iniciais:

| Código | Domínio |
| --- | --- |
| DEV | desenvolvimento e refatoração |
| REV | revisão de código e PR |
| CICD | pipelines, workflows e deploy |
| SEC | segurança e privacidade |
| OPS | runtime, observabilidade e remediação |
| DOC | documentação e arquitetura viva |

Exemplo:

```text
PDR-CICD-001-corrigir-falha-github-actions.md
```

## Versionamento e status

Cada PDR utiliza versão semântica:

- `MAJOR`: mudança incompatível no contrato de entrada, saída ou guardrails;
- `MINOR`: novo comportamento compatível;
- `PATCH`: correção editorial ou esclarecimento sem mudar o contrato.

Status permitidos:

- `draft`;
- `active`;
- `deprecated`;
- `superseded`.

## Responsabilidades do coordenador

O Coordenador de Prompts de Desenvolvimento deve:

1. identificar o objetivo real e a causa raiz conhecida;
2. selecionar ADRs e PDRs aplicáveis;
3. detectar conflitos entre instruções;
4. limitar o contexto ao necessário;
5. definir arquivos, contratos e comportamento esperado;
6. separar análise, implementação, revisão e validação;
7. exigir testes e evidências proporcionais ao risco;
8. impedir declarações de sucesso sem evidência;
9. registrar pendências e o próximo incremento.

## Política de criação

Criar um novo PDR quando pelo menos uma condição for atendida:

- fluxo recorrente;
- execução multiagentes;
- tarefa crítica ou de alto risco;
- necessidade de saída estruturada para automação;
- repetição de falhas por instrução ambígua;
- necessidade de governança entre ferramentas diferentes.

Não criar PDR para instruções pontuais, triviais ou sem potencial de reutilização.

## Rastreabilidade

Toda execução governada deve permitir navegar por:

```text
ADR aplicável
  → PDR utilizado e versão
  → issue ou solicitação
  → branch/commit
  → pull request
  → checks e evidências
  → decisão final
```

## Guardrails mínimos

- não armazenar segredos ou PII em prompts;
- não substituir requisitos por suposições silenciosas;
- preservar trabalho existente e aplicar a menor mudança correta;
- validar branch, mergeabilidade e CI antes de declarar conclusão;
- tratar falha de ferramenta como bloqueio evidenciado;
- registrar riscos, lacunas e rollback quando aplicável;
- usar ADR como autoridade em decisões transversais.

## Próximos incrementos

1. Criar `catalog.md` com todos os PDRs ativos.
2. Implementar catálogo YAML/JSON validável em CI.
3. Criar os PDRs iniciais para desenvolvimento, revisão de PR e correção de CI.
4. Integrar o catálogo ao coordenador de agentes do ReqSys.
5. Gerar manifesto de execução e evidências por PR.
