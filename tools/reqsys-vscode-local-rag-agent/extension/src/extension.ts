import * as vscode from 'vscode';
import { spawn } from 'child_process';
import * as path from 'path';

type AgentResult = {
  status: string;
  correlation_id?: string;
  answer?: string;
  restricoes?: string[];
  proximas_acoes?: string[];
  maturidade_percentual?: number;
  checks?: Array<{ name: string; status: string; detail: string }>;
  message?: string;
};

function getWorkspacePath(): string {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    throw new Error('Nenhum workspace aberto no VS Code.');
  }
  return folders[0].uri.fsPath;
}

function getAgentPath(context: vscode.ExtensionContext): string {
  return path.resolve(context.extensionPath, '..', 'agent');
}

function runAgent(context: vscode.ExtensionContext, args: string[]): Promise<AgentResult> {
  const cfg = vscode.workspace.getConfiguration('reqsys.agent');
  const pythonPath = cfg.get<string>('pythonPath') || 'python';
  const timeoutMs = cfg.get<number>('timeoutMs') || 60000;
  const agentPath = getAgentPath(context);

  return new Promise((resolve, reject) => {
    const child = spawn(pythonPath, ['-m', 'reqsys_agent.cli', ...args], {
      cwd: agentPath,
      env: { ...process.env, PYTHONPATH: agentPath }
    });

    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`Timeout ao executar agente local após ${timeoutMs}ms.`));
    }, timeoutMs);

    child.stdout.on('data', chunk => stdout += chunk.toString());
    child.stderr.on('data', chunk => stderr += chunk.toString());
    child.on('close', () => {
      clearTimeout(timer);
      try {
        resolve(JSON.parse(stdout) as AgentResult);
      } catch {
        reject(new Error(`Falha ao interpretar retorno do agente. STDERR=${stderr}; STDOUT=${stdout}`));
      }
    });
    child.on('error', reject);
  });
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderResult(result: AgentResult): string {
  const restricoes = result.restricoes || [];
  const proximas = result.proximas_acoes || [];
  const checks = result.checks || [];
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><style>
    body { font-family: system-ui, sans-serif; padding: 20px; line-height: 1.45; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 14px; margin: 12px 0; }
    .green { border-left: 8px solid #16a34a; }
    .yellow { border-left: 8px solid #ca8a04; }
    .red { border-left: 8px solid #dc2626; }
    table { border-collapse: collapse; width: 100%; }
    td, th { border: 1px solid #ddd; padding: 8px; }
  </style></head><body>
  <h1>ReqSys Local RAG Agent</h1>
  <div class="card ${result.status === 'ok' ? 'green' : result.status === 'attention' ? 'yellow' : 'red'}">
    <strong>Status:</strong> ${escapeHtml(result.status || 'indefinido')}<br/>
    <strong>Correlation ID:</strong> ${escapeHtml(result.correlation_id || 'não informado')}<br/>
    ${typeof result.maturidade_percentual === 'number' ? `<strong>Maturidade:</strong> ${result.maturidade_percentual}%` : ''}
  </div>
  ${result.answer ? `<div class="card"><h2>Resposta</h2><p>${escapeHtml(result.answer)}</p></div>` : ''}
  ${checks.length ? `<div class="card"><h2>Checklist</h2><table><tr><th>Item</th><th>Status</th><th>Detalhe</th></tr>${checks.map(c => `<tr><td>${escapeHtml(c.name)}</td><td>${escapeHtml(c.status)}</td><td>${escapeHtml(c.detail)}</td></tr>`).join('')}</table></div>` : ''}
  ${restricoes.length ? `<div class="card yellow"><h2>O que não pode fazer</h2><ul>${restricoes.map(r => `<li>${escapeHtml(r)}</li>`).join('')}</ul></div>` : ''}
  ${proximas.length ? `<div class="card"><h2>Próximas ações</h2><ol>${proximas.map(a => `<li>${escapeHtml(a)}</li>`).join('')}</ol></div>` : ''}
  </body></html>`;
}

async function showResult(title: string, result: AgentResult): Promise<void> {
  const panel = vscode.window.createWebviewPanel('reqsysLocalRagAgent', title, vscode.ViewColumn.One, { enableScripts: false });
  panel.webview.html = renderResult(result);
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(vscode.commands.registerCommand('reqsys.openPanel', async () => {
    const result = await runAgent(context, ['health']);
    await showResult('ReqSys Painel Operacional', result);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('reqsys.indexProject', async () => {
    const result = await runAgent(context, ['index', '--workspace', getWorkspacePath()]);
    await showResult('ReqSys Indexação do Projeto', result);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('reqsys.askProject', async () => {
    const question = await vscode.window.showInputBox({ title: 'ReqSys: Perguntar ao Projeto', prompt: 'Informe a pergunta.', ignoreFocusOut: true });
    if (!question) return;
    const result = await runAgent(context, ['ask', '--workspace', getWorkspacePath(), '--question', question]);
    await showResult('ReqSys Pergunta ao Projeto', result);
  }));

  context.subscriptions.push(vscode.commands.registerCommand('reqsys.governanceChecklist', async () => {
    const result = await runAgent(context, ['governance', '--workspace', getWorkspacePath()]);
    await showResult('ReqSys Checklist Padrão Ouro', result);
  }));
}

export function deactivate(): void {}
