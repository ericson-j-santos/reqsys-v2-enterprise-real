# ADR-045 — Governança e Coordenação de Prompts de Desenvolvimento

Status: proposto
Data: 2026-07-20

## Contexto

O ReqSys possui ADRs para registrar decisões arquiteturais e um coordenador de agentes orientado por ADR. Entretanto, as instruções usadas para análise, geração, revisão e correção de código ainda podem ficar dispersas em conversas, issues, PRs, agentes ou automações.

Essa dispersão cria riscos de:

- instruções conflitantes entre agentes;
- geração de código sem aderência aos ADRs vigentes;
- perda de contexto, critérios de aceite e evidências;
- repetição de prompts e retrabalho;
- ausência de versionamento, autoria e rastreabilidade;
- execução de mudanças sem validação proporcional ao risco.

## Decisão

Criar uma disciplina separada e integrada de **Prompt Development Governance**, mantendo responsabilidades distintas:

- **ADR** registra decisões arquiteturais duráveis, seus trade-offs e impactos;
- **Prompt Development Record (PDR)** registra contratos operacionais versionados para orientar análise, implementação, revisão, testes e entrega de código;
- **Coordenador de Prompts de Desenvolvimento** seleciona ADRs, PDRs, contexto, agentes, validações e evidências necessárias para cada incremento.

A fonte canônica dos PDRs será `docs/prompts/`.

## Modelo de coordenação

O coordenador deve executar o seguinte fluxo:

1. Classificar a solicitação: análise, correção, incremento, refatoração, segurança, CI/CD, documentação ou operação.
2. Resolver ADRs aplicáveis por domínio e dependência.
3. Selecionar um PDR existente ou criar proposta de novo PDR quando houver reutilização esperada.
4. Construir o contexto mínimo necessário, sem incluir segredos ou dados pessoais.
5. Definir contrato de saída: arquivos, comportamento, critérios de aceite, testes e evidências.
6. Designar agentes ou etapas especializadas.
7. Executar validações proporcionais ao risco.
8. Registrar resultado, desvios, evidências e pendências.

## Estrutura canônica

```text
docs/
├── adr/
│   └── ADR-NNN-*.md
└── prompts/
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

## Contrato mínimo de um PDR

Cada PDR deve possuir:

- identificador estável;
- título e objetivo;
- versão e status;
- domínio e tipo de tarefa;
- ADRs obrigatórios e relacionados;
- entradas obrigatórias e opcionais;
- restrições e guardrails;
- sequência de execução;
- formato de saída;
- critérios de aceite;
- validações e evidências;
- estratégia de falha, escalonamento e rollback;
- histórico de alterações.

## Guardrails

1. PDR não pode contrariar ADR aceito.
2. Segurança, privacidade, autenticação e produção sempre consultam os ADRs fundacionais aplicáveis.
3. Prompts não armazenam tokens, senhas, chaves, PII ou conteúdo confidencial não mascarado.
4. Geração de código deve declarar arquivos afetados, riscos e testes.
5. Alterações de alto risco exigem revisão humana e evidência de CI.
6. O coordenador não deve declarar sucesso sem evidência verificável.
7. Mudanças transversais identificadas durante a execução devem gerar proposta de ADR, não apenas alteração de prompt.

## Consequências

### Positivas

- separação clara entre decisão arquitetural e instrução operacional;
- prompts reutilizáveis, versionados e auditáveis;
- redução de conflito entre agentes e automações;
- maior aderência do código aos ADRs;
- melhor rastreabilidade entre solicitação, implementação, testes, PR e evidência.

### Trade-offs

- maior disciplina documental;
- necessidade de manter catálogo e versões;
- risco de excesso de burocracia se PDRs forem criados para tarefas triviais.

Para reduzir esse risco, PDR é obrigatório apenas para fluxos recorrentes, críticos, multiagentes ou com impacto transversal.

## Critérios de aceite

- `docs/prompts/README.md` criado com política e fluxo operacional;
- template de PDR versionado;
- ADR indexado no catálogo padrão ouro;
- relação ADR → PDR → execução → evidência documentada;
- convenção de identificação e versionamento definida;
- próximo incremento registrado para implementação do catálogo e do coordenador executável.

## Próximo incremento

Implementar um catálogo legível por máquina e um serviço coordenador que:

- descubra ADRs e PDRs aplicáveis;
- valide dependências e conflitos;
- gere plano de execução estruturado;
- associe agentes especializados;
- produza um manifesto de evidências para PR e CI.
