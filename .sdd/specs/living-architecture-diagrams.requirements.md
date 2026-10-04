# Arquitetura Viva para diagramas e fluxos navegáveis

## Objetivo
Recuperar e consolidar no PR #44 a base de Arquitetura Viva originalmente implementada, adaptando sua integração aos catálogos e gates atuais do ReqSys sem sobrescrever evoluções posteriores da main.

## Requisitos
1. A documentação define fonte, versão, ambiente, auditoria, segurança e nível de confiança.
2. O contrato TypeScript modela fontes, nós, arestas, auditoria, ambiente e confiança.
3. O gerador Mermaid falha fechado sem fonte rastreável ou ambiente e sanitiza labels.
4. A UI /arquitetura-viva apresenta fluxo navegável, filtro, inspector, dependências, metadados e gates.
5. A UI declara explicitamente que runtime real/OpenTelemetry ainda não estão integrados.
6. A rota está no router, catálogo de navegação, catálogo responsivo e governança ReqSys 360.
7. A navegação e o inspector permanecem utilizáveis em viewport móvel sem overflow horizontal.
8. Nenhum artefato expõe segredo, token, senha, PII ou credencial real.

## Critérios de aceite
- tests/test_living_architecture_contract.py verde no HEAD atual.
- frontend/tests/e2e/responsividade.spec.js cobre a rota e o fluxo específico de seleção, filtro e ausência de overflow.
- Build, navegação, design tokens, segurança e Pre-PR Readiness ficam verdes no mesmo HEAD.
- behind_by=0 e nenhum deploy/promoção de ambiente é executado.

9. O Pre-PR deve instalar dependências backend quando um teste raiz selecionado executar script que importa `app.*`.
10. O inventário ReqSys 360 não pode promover arquivos `*.test.js` ou `*.spec.js` a candidatos de serviço órfão.

## Prevenção de recorrência
- A inferência transitiva do perfil backend possui testes positivo e negativo.
- O inventário de serviços possui regressão explícita para arquivos de teste.
- O gate de linguagem simples continua bloqueando termos técnicos proibidos na interface.
