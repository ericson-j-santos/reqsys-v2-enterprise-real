import type { ArchitectureDiagram, DiagramRendererResult } from '../contracts/diagram.contract';

function sanitizeMermaidLabel(value: string): string {
  return value
    .replace(/[\r\n]+/g, ' ')
    .replace(/[\[\]{}<>]/g, '')
    .trim();
}

export function gerarMermaidFlowchart(diagram: ArchitectureDiagram): DiagramRendererResult {
  if (!diagram.sources?.length) {
    throw new Error('Nao foi possivel gerar diagrama sem fonte rastreavel.');
  }

  if (!diagram.environment) {
    throw new Error('Nao foi possivel gerar diagrama sem ambiente informado.');
  }

  const lines: string[] = ['flowchart LR'];

  for (const node of diagram.nodes) {
    const label = sanitizeMermaidLabel(node.label);
    lines.push(`  ${node.id}["${label}"]`);
  }

  for (const edge of diagram.edges) {
    const label = edge.label ? `|${sanitizeMermaidLabel(edge.label)}|` : '';
    lines.push(`  ${edge.from} -->${label} ${edge.to}`);
  }

  const metadata = [
    `%% id: ${diagram.id}`,
    `%% title: ${diagram.title}`,
    `%% version: ${diagram.version}`,
    `%% environment: ${diagram.environment}`,
    `%% generatedAt: ${diagram.audit.generatedAt}`,
    `%% generatedBy: ${diagram.audit.generatedBy}`,
    `%% confidence: ${diagram.audit.confidence}`,
    `%% hash: ${diagram.audit.hash}`,
  ];

  return {
    format: 'mermaid',
    content: [...metadata, ...lines].join('\n'),
    diagram,
  };
}
