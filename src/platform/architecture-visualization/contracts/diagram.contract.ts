export type ArchitectureEnvironment = 'dev' | 'homologacao' | 'producao';

export type ArchitectureConfidence = 'alta' | 'media' | 'baixa';

export type ArchitectureSourceType =
  | 'codigo'
  | 'openapi'
  | 'schema'
  | 'log'
  | 'trace'
  | 'dashboard'
  | 'adr'
  | 'manual';

export interface ArchitectureSource {
  id: string;
  type: ArchitectureSourceType;
  name: string;
  path?: string;
  version?: string;
  hash?: string;
  capturedAt?: string;
}

export interface ArchitectureNode {
  id: string;
  label: string;
  type: string;
  description?: string;
  owner?: string;
  environment?: ArchitectureEnvironment;
  metadata?: Record<string, unknown>;
}

export interface ArchitectureEdge {
  id: string;
  from: string;
  to: string;
  label?: string;
  type?: string;
  metadata?: Record<string, unknown>;
}

export interface ArchitectureDiagramAudit {
  generatedAt: string;
  generatedBy: string;
  correlationId?: string;
  hash: string;
  confidence: ArchitectureConfidence;
}

export interface ArchitectureDiagram {
  id: string;
  title: string;
  version: string;
  environment: ArchitectureEnvironment;
  sources: ArchitectureSource[];
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  audit: ArchitectureDiagramAudit;
}

export interface DiagramRendererResult {
  format: 'mermaid' | 'd2' | 'bpmn' | 'react-flow';
  content: string;
  diagram: ArchitectureDiagram;
}
