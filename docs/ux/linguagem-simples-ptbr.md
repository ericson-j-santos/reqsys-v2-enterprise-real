# Linguagem simples PT-BR no ReqSys

## Objetivo

Garantir que pessoas usuárias consigam operar o ReqSys sem depender de jargões técnicos, corporativos ou termos genéricos em inglês.

## Escopo obrigatório

A regra se aplica a todo texto apresentado às pessoas na interface: títulos, menus, descrições, avisos, botões, mensagens estáticas, rótulos, textos de ajuda, atributos de acessibilidade e nomes de telas.

Identificadores internos não são traduzidos quando a alteração puder quebrar contratos. Isso inclui caminhos de rota, nomes de campos, nomes de funções, parâmetros de integração e valores exigidos por serviços externos. A interface deve traduzir esses conceitos antes de apresentá-los.

## Exceções permitidas

Nomes próprios de produtos e serviços permanecem como registrados pelo fornecedor, por exemplo: GitHub, Teams, Planner, Power Automate, Power Apps, Figma, Copilot, Codex e ReqSys.

Uma exceção nunca autoriza o uso de jargão genérico ao redor do nome próprio. Exemplo: "GitHub" é permitido; "GitHub Launchpad" não é. Deve-se preferir "Ações do GitHub" ou equivalente em português.

## Vocabulário preferencial

| Evitar | Usar na interface |
| --- | --- |
| dashboard | painel |
| runtime | execução |
| work item | item de trabalho |
| launchpad | ações / central de ações |
| branch | versão de código / ramificação |
| merge | integração de alterações |
| dry-run | simulação |
| readiness | prontidão |
| score | nota / índice |
| analytics | indicadores / análise |
| low-code | automações / automação de baixo código |
| status | situação |
| cache | armazenamento temporário |
| mock | simulação |
| specs | especificações |
| feature | funcionalidade |
| gate | verificação obrigatória |
| backend | serviço |
| frontend | aplicação / interface |
| pipeline | fluxo |
| workspace | área de trabalho |
| showcase | demonstração |
| login | entrar / acesso |
| CI/CD | integração e publicação automáticas |
| CI | verificações automáticas |
| PR | solicitação de integração |
| API | serviço / integração |
| URL | endereço |
| LLM | modelo de IA |
| PII | dados pessoais |
| SDD | especificação da solução |
| ALM | administração do ciclo de entrega |
| ADR | decisão de arquitetura |
| DEV | desenvolvimento |
| STG | homologação |
| PROD | produção |

## Critério de conclusão

Uma alteração de interface está concluída quando:

1. o verificador `frontend/scripts/validate-user-facing-language.mjs` retorna zero ocorrências proibidas;
2. os testes do verificador são aprovados;
3. a construção do frontend é aprovada;
4. os demais checks obrigatórios do repositório permanecem aprovados;
5. nenhuma rota, contrato de integração ou identificador técnico foi alterado apenas para traduzir texto visível.

## Proteção contra regressão

O workflow `Linguagem simples PT-BR` executa em solicitações de integração que alterem a interface ou o próprio verificador. Quando encontra um termo proibido, informa arquivo, linha, termo e substituição sugerida.

A lista de termos deve evoluir por incremento: novos termos identificados devem ser incluídos no verificador e corrigidos no mesmo conjunto de mudanças, evitando criar uma lista permanente de dívidas conhecidas.
