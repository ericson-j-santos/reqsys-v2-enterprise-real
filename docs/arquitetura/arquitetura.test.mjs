/**
 * Testes para docs/arquitetura/index.html (visualizador dinâmico)
 * Execute com: node arquitetura.test.mjs
 * Requer Node.js 18+
 */

import { readFileSync } from "node:fs";
import { test, describe } from "node:test";
import assert from "node:assert/strict";

const HTML_FILE = new URL(
  "./index.html",
  import.meta.url
).pathname.replace(/^\/([A-Z]:)/, "$1");

let html;
try {
  html = readFileSync(HTML_FILE, "utf-8");
} catch {
  console.error(`Arquivo não encontrado: ${HTML_FILE}`);
  process.exit(1);
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const count = (pattern) => (html.match(pattern) ?? []).length;
const has = (pattern) => pattern.test(html);

// ─── Estrutura HTML ──────────────────────────────────────────────────────────

describe("Estrutura HTML", () => {
  test("possui declaração DOCTYPE", () => {
    assert.ok(has(/<!doctype\s+html>/i), "Falta <!DOCTYPE html>");
  });

  test("tag <html> tem lang='pt-br'", () => {
    assert.ok(has(/lang="pt-br"/i), 'Atributo lang="pt-br" ausente');
  });

  test("charset UTF-8 declarado", () => {
    assert.ok(
      has(/charset=["']?UTF-8["']?/i),
      "Meta charset UTF-8 não encontrado"
    );
  });

  test("título da página está correto", () => {
    const match = html.match(/<title>(.*?)<\/title>/i);
    assert.ok(match, "Tag <title> ausente");
    assert.match(
      match[1],
      /ReqSys/i,
      "Título não menciona ReqSys"
    );
  });

  test("tem tag <body> e </body>", () => {
    assert.ok(has(/<body>/i), "Tag <body> ausente");
    assert.ok(has(/<\/body>/i), "Tag </body> ausente");
  });

  test("tem tag <head> e </head>", () => {
    assert.ok(has(/<head>/i), "Tag <head> ausente");
    assert.ok(has(/<\/head>/i), "Tag </head> ausente");
  });
});

// ─── Cabeçalhos e Seções ────────────────────────────────────────────────────

describe("Cabeçalhos e Seções", () => {
  test("tem exatamente um <h1> com 'ReqSys'", () => {
    const h1s = html.match(/<h1[^>]*>.*?<\/h1>/gi) ?? [];
    assert.equal(h1s.length, 1, `Esperado 1 <h1>, encontrado ${h1s.length}`);
    assert.match(h1s[0], /ReqSys/i, "h1 não menciona ReqSys");
  });

  test("tem exatamente 4 seções <h2>", () => {
    const h2Count = count(/<h2[^>]*>/gi);
    assert.equal(h2Count, 4, `Esperado 4 <h2>, encontrado ${h2Count}`);
  });

  test("seção 1 - Arquitetura Geral presente", () => {
    assert.ok(has(/Arquitetura Geral/i), "Seção 'Arquitetura Geral' ausente");
  });

  test("seção 2 - Modelo de Dados presente", () => {
    assert.ok(
      has(/Modelo de Dados/i),
      "Seção 'Modelo de Dados' ausente"
    );
  });

  test("seção 3 - Fluxo de Deploy presente", () => {
    assert.ok(
      has(/Fluxo de Deploy/i),
      "Seção 'Fluxo de Deploy/Validação' ausente"
    );
  });

  test("seção 4 - Ambientes, URLs e Credenciais presente", () => {
    assert.ok(
      has(/Ambientes.*URLs.*Credenciais|Credenciais.*URLs.*Ambientes/i),
      "Seção 'Ambientes, URLs e Credenciais' ausente"
    );
  });
});

// ─── Mermaid ─────────────────────────────────────────────────────────────────

describe("Integração Mermaid", () => {
  test("script do Mermaid é carregado via CDN", () => {
    assert.ok(
      has(/cdn\.jsdelivr\.net\/npm\/mermaid/i),
      "Script Mermaid CDN não encontrado"
    );
  });

  test("mermaid.initialize é chamado", () => {
    assert.ok(
      has(/mermaid\.initialize\s*\(/),
      "mermaid.initialize() ausente"
    );
  });

  test("startOnLoad está habilitado", () => {
    assert.ok(
      has(/startOnLoad\s*:\s*true/),
      "startOnLoad: true não encontrado"
    );
  });

  test("tem exatamente 4 blocos <div class=\"mermaid\">", () => {
    const divCount = count(/<div\s+class="mermaid"/gi);
    assert.equal(
      divCount,
      4,
      `Esperado 4 divs .mermaid, encontrado ${divCount}`
    );
  });
});

// ─── Diagrama 1 - Arquitetura Geral ──────────────────────────────────────────

describe("Diagrama 1 - Arquitetura Geral (flowchart)", () => {
  test("declara flowchart TD", () => {
    assert.ok(has(/flowchart\s+TD/), "flowchart TD não encontrado");
  });

  test("contém nó Frontend (Vue 3)", () => {
    assert.ok(has(/Vue\s*3/i), "Vue 3 não mencionado no diagrama");
  });

  test("contém nó Backend (FastAPI)", () => {
    assert.ok(has(/FastAPI/i), "FastAPI não mencionado no diagrama");
  });

  test("contém Redis", () => {
    assert.ok(has(/Redis/), "Redis não mencionado no diagrama");
  });

  test("contém SQL Server/SQLite", () => {
    assert.ok(
      has(/SQL\s*Server|SQLite/i),
      "SQL Server/SQLite não mencionado no diagrama"
    );
  });

  test("contém Docker Compose", () => {
    assert.ok(has(/Docker\s*Compose/i), "Docker Compose não mencionado");
  });

  test("contém Nginx", () => {
    assert.ok(has(/Nginx/i), "Nginx não mencionado");
  });

  test("menciona integração com Power BI", () => {
    assert.ok(has(/Power\s*BI/i), "Power BI não mencionado");
  });

  test("menciona integração com Redmine", () => {
    assert.ok(has(/Redmine/i), "Redmine não mencionado");
  });

  test("menciona integração com GitHub", () => {
    assert.ok(has(/GitHub/i), "GitHub não mencionado");
  });
});

// ─── Diagrama 2 - Modelo de Dados ────────────────────────────────────────────

describe("Diagrama 2 - Modelo de Dados (erDiagram)", () => {
  test("declara erDiagram", () => {
    assert.ok(has(/erDiagram/), "erDiagram não encontrado");
  });

  test("entidade USUARIO definida", () => {
    assert.ok(has(/USUARIO/), "Entidade USUARIO ausente");
  });

  test("entidade SESSAO definida", () => {
    assert.ok(has(/SESSAO/), "Entidade SESSAO ausente");
  });

  test("entidade SOLICITACAO definida", () => {
    assert.ok(has(/SOLICITACAO/), "Entidade SOLICITACAO ausente");
  });

  test("entidade ANEXO definida", () => {
    assert.ok(has(/ANEXO/), "Entidade ANEXO ausente");
  });

  test("entidade LOG definida", () => {
    assert.ok(has(/\bLOG\b/), "Entidade LOG ausente");
  });

  test("relação USUARIO -> SESSAO existe", () => {
    assert.ok(
      has(/USUARIO\s*\|.*SESSAO/),
      "Relação USUARIO -> SESSAO ausente"
    );
  });

  test("relação USUARIO -> SOLICITACAO existe", () => {
    assert.ok(
      has(/USUARIO\s*\|.*SOLICITACAO/),
      "Relação USUARIO -> SOLICITACAO ausente"
    );
  });

  test("campo email em USUARIO", () => {
    assert.ok(has(/email/), "Campo email não encontrado em USUARIO");
  });

  test("campo token em SESSAO", () => {
    assert.ok(has(/token/), "Campo token não encontrado em SESSAO");
  });
});

// ─── Diagrama 3 - Fluxo de Deploy ────────────────────────────────────────────

describe("Diagrama 3 - Fluxo de Deploy (stateDiagram-v2)", () => {
  test("declara stateDiagram-v2", () => {
    assert.ok(has(/stateDiagram-v2/), "stateDiagram-v2 não encontrado");
  });

  test("estado inicial [*] presente", () => {
    assert.ok(has(/\[\*\]/), "Estado inicial [*] ausente");
  });

  test("estado ValidarAmbiente presente", () => {
    assert.ok(has(/ValidarAmbiente/), "Estado ValidarAmbiente ausente");
  });

  test("estado SubirServicos presente", () => {
    assert.ok(has(/SubirServicos/), "Estado SubirServicos ausente");
  });

  test("estado TestarAcesso presente", () => {
    assert.ok(has(/TestarAcesso/), "Estado TestarAcesso ausente");
  });

  test("estado Login presente", () => {
    assert.ok(has(/\bLogin\b/), "Estado Login ausente");
  });

  test("estado Erro presente", () => {
    assert.ok(has(/\bErro\b/), "Estado Erro ausente");
  });

  test("menciona docker-compose up", () => {
    assert.ok(
      has(/docker-compose\s+up/i),
      "Ação 'docker-compose up' não encontrada"
    );
  });
});

// ─── Diagrama 4 - Ambientes e URLs ───────────────────────────────────────────

describe("Diagrama 4 - Ambientes, URLs e Credenciais (flowchart)", () => {
  test("porta do frontend Dev (8083) presente", () => {
    assert.ok(has(/8083/), "Porta 8083 (Dev frontend) não encontrada");
  });

  test("porta do frontend Prod (8081) presente", () => {
    assert.ok(has(/8081/), "Porta 8081 (Prod frontend) não encontrada");
  });

  test("porta do frontend Test (8084) presente", () => {
    assert.ok(has(/8084/), "Porta 8084 (Test frontend) não encontrada");
  });

  test("porta da API Dev (8211) presente", () => {
    assert.ok(has(/8211/), "Porta 8211 (API Dev) não encontrada");
  });

  test("porta da API Prod (8210) presente", () => {
    assert.ok(has(/8210/), "Porta 8210 (API Prod) não encontrada");
  });

  test("porta da API Test (8212) presente", () => {
    assert.ok(has(/8212/), "Porta 8212 (API Test) não encontrada");
  });

  test("credencial admin@demo.com presente", () => {
    assert.ok(
      has(/admin@demo\.com/),
      "Credencial admin@demo.com não encontrada"
    );
  });

  test("nós DB SQLite e SQL Server presentes", () => {
    assert.ok(has(/SQLite/), "SQLite ausente no diagrama de ambientes");
    assert.ok(has(/SQL\s*Server/i), "SQL Server ausente no diagrama de ambientes");
  });

  test("redis presente em todos os ambientes", () => {
    const redisCount = count(/Redis/gi);
    assert.ok(
      redisCount >= 3,
      `Esperado Redis ao menos 3 vezes (dev/prod/test), encontrado ${redisCount}`
    );
  });
});

// ─── Estilo e Acessibilidade ─────────────────────────────────────────────────

describe("Estilo e Acessibilidade", () => {
  test("CSS inline define font-family", () => {
    assert.ok(has(/font-family/), "font-family não definido no CSS");
  });

  test("CSS define cor para h2", () => {
    assert.ok(
      has(/h2\s*\{[^}]*color\s*:/),
      "Cor para h2 não definida no CSS"
    );
  });

  test("bloco .mermaid tem border-radius", () => {
    assert.ok(
      has(/\.mermaid\s*\{[^}]*border-radius/s),
      "border-radius não definido para .mermaid"
    );
  });

  test("footer presente com texto de geração", () => {
    assert.ok(has(/<footer/i), "Tag <footer> ausente");
    assert.ok(
      has(/Gerado\s+automaticamente/i),
      "Texto 'Gerado automaticamente' ausente no footer"
    );
  });
});
