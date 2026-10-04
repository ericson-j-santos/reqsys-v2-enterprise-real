# Architecture Visualization Engine

## Objetivo

Módulo transversal responsável por gerar, versionar, auditar e explicar diagramas e fluxos vivos a partir de fontes confiáveis do ReqSys.

## Responsabilidades

- Ler metadados de código, rotas, contratos, schemas, logs, traces e analytics.
- Gerar diagramas Mermaid, D2, BPMN ou grafos navegáveis.
- Relacionar requisitos, código, runtime, dados e indicadores.
- Preservar rastreabilidade, versionamento e auditoria.
- Permitir explicação por IA com fontes e nível de confiabilidade.

## Estrutura Recomendada

```text
architecture-visualization/
  README.md
  contracts/
    diagram.contract.ts
    source-metadata.contract.ts
  parsers/
    code-parser.ts
    openapi-parser.ts
    schema-parser.ts
  generators/
    mermaid-generator.ts
    d2-generator.ts
  lineage/
    analytics-lineage.ts
    dependency-graph.ts
  runtime/
    trace-linker.ts
    correlation-mapper.ts
  ai/
    architecture-explainer.ts
  renderers/
    react-flow-adapter.ts
```

## Contrato Conceitual

```ts
export interface ArchitectureDiagram {
  id: string;
  title: string;
  version: string;
  environment: 'dev' | 'homologacao' | 'producao';
  sources: ArchitectureSource[];
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  generatedAt: string;
  generatedBy: string;
  correlationId?: string;
  hash: string;
  confidence: 'alta' | 'media' | 'baixa';
}
```

## Gates Obrigatórios

A engine deve bloquear publicação quando:

- houver segredo, token, senha, CPF ou PII exposta;
- não existir fonte rastreável;
- o ambiente não estiver identificado;
- o diagrama não tiver versão;
- a IA gerar explicação sem indicar fonte e confiabilidade;
- houver divergência crítica entre código e documentação.

## Próximos Incrementos

1. Criar contratos TypeScript reais.
2. Criar gerador Mermaid inicial.
3. Criar adaptador visual com React Flow.
4. Integrar rotas/API.
5. Integrar analytics/lineage.
6. Integrar OpenTelemetry/correlation_id.
