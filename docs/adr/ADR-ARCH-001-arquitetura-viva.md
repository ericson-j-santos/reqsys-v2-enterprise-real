# ADR-ARCH-001 — Arquitetura Viva para Diagramas e Fluxos

## Status

Aceita.

## Data

2026-06-20.

## Contexto

O ReqSys e as aplicações corporativas associadas precisam evoluir de documentação estática para uma abordagem de arquitetura viva. Diagramas, fluxos e mapas de dependência devem refletir o estado real do código, das integrações, dos dados, do runtime, dos ambientes e dos indicadores analíticos.

A documentação tradicional em arquivos estáticos tende a ficar obsoleta, perde rastreabilidade e não permite análise de impacto confiável. A decisão é criar uma capacidade transversal para geração, navegação, versionamento, auditoria e explicação por IA de diagramas e fluxos.

## Decisão

Adotar o padrão de Arquitetura Viva como capacidade transversal do ecossistema ReqSys.

Diagramas e fluxos devem ser:

- vivos;
- automáticos;
- navegáveis;
- integrados ao runtime;
- integrados ao código;
- integrados ao analytics;
- versionados;
- auditáveis;
- explicáveis por IA.

## Escopo Inicial

A primeira implementação deve criar a base canônica de documentação, estrutura técnica e contratos para evolução incremental. A geração automática completa será adicionada em incrementos posteriores, preservando compatibilidade com CI/CD, segurança e governança.

## Fontes de Informação

A engine deve combinar, quando disponível:

- código-fonte;
- rotas e contratos OpenAPI;
- schemas de banco;
- eventos e logs estruturados;
- traces OpenTelemetry;
- dashboards e datasets analíticos;
- ADRs e documentação funcional;
- metadados de deploy e ambientes.

## Componentes Arquiteturais

- `diagram-parser`: interpreta fontes técnicas e funcionais.
- `schema-reader`: interpreta schemas e contratos.
- `flow-engine`: constrói fluxos de negócio e integração.
- `lineage-engine`: mapeia origem, transformação e consumo dos dados.
- `graph-builder`: monta grafo navegável.
- `mermaid-generator`: gera diagramas Mermaid.
- `d2-generator`: gera diagramas D2.
- `runtime-mapper`: relaciona traces e eventos ao fluxo.
- `observability-linker`: conecta logs, métricas e traces.
- `ai-explainer`: explica arquitetura, impactos, riscos e dependências.

## Padrões de Governança

Todo diagrama ou fluxo gerado deve conter:

- identificador único;
- versão;
- data/hora de geração;
- fonte de origem;
- ambiente relacionado;
- hash ou checksum do conteúdo;
- autor humano ou agente responsável;
- correlation_id quando derivado de runtime;
- trilha de auditoria;
- indicação de confiabilidade.

## Segurança

É proibido expor em diagramas:

- tokens;
- senhas;
- connection strings;
- CPF, PII ou dados sensíveis;
- segredos de integração;
- nomes internos sensíveis sem classificação adequada.

A geração deve aplicar mascaramento e classificação de informação antes da publicação.

## Gates de Produção

A funcionalidade não deve ser promovida para produção se:

- gerar diagrama sem fonte rastreável;
- expor segredo ou PII;
- omitir ambiente de origem;
- não registrar auditoria;
- não informar versão;
- não preservar histórico;
- não possuir fallback seguro quando a IA falhar;
- gerar explicação sem indicar incerteza/confiabilidade.

## Consequências

### Positivas

- Reduz obsolescência documental.
- Melhora análise de impacto.
- Facilita auditoria e governança.
- Conecta requisitos, código, runtime e analytics.
- Permite navegação técnica e executiva.

### Atenções

- Exige disciplina de metadados.
- Exige tratamento de segurança e LGPD.
- Exige validação de fontes para evitar diagramas inventados.
- Deve evoluir incrementalmente para não bloquear entregas.

## Decisão Final

Arquitetura Viva passa a ser padrão canônico para ReqSys e aplicações correlatas. Diagramas estáticos podem existir, mas devem ser derivados, versionados ou rastreados a partir de fontes confiáveis sempre que possível.
