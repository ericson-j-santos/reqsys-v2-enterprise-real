# Padrão Ouro Enterprise

## Objetivo

Estabelecer o baseline obrigatório para evolução do ReqSys e demais soluções corporativas: rastreabilidade, segurança, qualidade, observabilidade, documentação viva, analytics navegável e IA auditável.

## Ciclo operacional obrigatório

```text
Planejar → versionar → implementar → testar → validar CI → revisar → publicar → monitorar → documentar → evoluir
```

Nenhuma alteração deve avançar para produção sem evidência mínima de requisito, branch, PR, validação, revisão e rastreabilidade.

## Princípios

1. Git é a fonte da verdade.
2. CI/CD é gate de qualidade, não apenas automação de build.
3. Produção só recebe mudanças validadas.
4. Documentação deve ser viva, versionada e rastreável.
5. Indicadores relevantes devem permitir drill-down analítico.
6. Decisões relevantes devem possuir ADR.
7. Logs devem conter `correlation_id` e não podem expor PII, tokens, senhas ou connection strings.
8. IA deve operar com fontes, confiança, auditoria e fallback seguro.
9. Ambientes `dev`, `homologação` e `produção` devem ser explícitos.
10. Mudanças devem ser pequenas, revisáveis e testáveis.

## Gates bloqueantes de produção

Produção deve ser bloqueada quando existir qualquer condição abaixo:

- autenticação desligada;
- CORS com `*`;
- JWT sem validação real de issuer/audience;
- segredo, token, senha, CPF, PII ou connection string em log ou código;
- consulta IA sem fontes quando fontes forem obrigatórias;
- resposta IA inventada sem base rastreável;
- ingestão sem permissão administrativa;
- auditoria sem `correlation_id`;
- conector administrativo exposto sem controle;
- CI vermelho, ausente ou inconclusivo;
- PR sem evidências mínimas.

## Checklist de demanda padrão ouro

- [ ] Requisito descrito de forma clara.
- [ ] Critérios de aceite definidos.
- [ ] Impacto funcional, técnico e operacional avaliado.
- [ ] Ambiente alvo identificado.
- [ ] Decisão técnica registrada em ADR, quando aplicável.
- [ ] Riscos e rollback mapeados.
- [ ] Testes definidos.
- [ ] Observabilidade definida.
- [ ] Analytics/drill-down avaliado.
- [ ] Documentação e changelog atualizados.

## Checklist de PR padrão ouro

- [ ] Branch segue convenção.
- [ ] PR possui objetivo, escopo e fora de escopo.
- [ ] Evidências de build/testes anexadas.
- [ ] Segurança revisada.
- [ ] Logs e PII revisados.
- [ ] Ambientes afetados informados.
- [ ] Documentação atualizada.
- [ ] CHANGELOG atualizado, quando aplicável.
- [ ] CI verde antes de ready for review.
- [ ] Merge somente após validação.

## Modelo analítico obrigatório

Sempre que fizer sentido, aplicar o fluxo:

```text
Indicador → gráfico → analítico filtrado → detalhe → ação operacional
```

Exemplos de ações operacionais:

- abrir issue;
- reprocessar integração;
- exportar evidência;
- abrir log correlacionado;
- visualizar histórico;
- acionar responsável.

## Arquitetura viva

Diagramas e fluxos devem ser tratados como parte do produto:

- vivos;
- automáticos;
- navegáveis;
- integrados ao runtime;
- integrados ao código;
- integrados ao analytics;
- versionados;
- auditáveis;
- explicáveis por IA.

## Schema-Driven UI / Dynamic Data Renderer

Quando houver dados variáveis, priorizar backend retornando:

- `schema`;
- `data`;
- `metadata`;
- permissões;
- filtros;
- ordenação;
- máscaras;
- ações disponíveis.

O frontend deve renderizar tabelas, cards, detalhes, filtros e formulários com baixo acoplamento a nomes fixos de colunas.

## IA corporativa auditável

Fluxo mínimo:

```text
Entrada → validação → contexto/RAG → execução → fontes → resposta → auditoria
```

Regras mínimas:

- responder com fontes quando houver consulta a bases;
- registrar confiança;
- bloquear alucinação sem base;
- separar prompt, contexto e resposta;
- auditar pergunta, resposta, fonte, usuário, data e `correlation_id`;
- aplicar fallback quando não houver evidência suficiente.

## Estrutura documental recomendada

```text
docs/
  ADR/
  arquitetura/
  governanca/
  seguranca/
  observabilidade/
  analytics/
  ambientes/
  runbooks/
.github/
  workflows/
  pull_request_template.md
README.md
CHANGELOG.md
ROADMAP.md
```
