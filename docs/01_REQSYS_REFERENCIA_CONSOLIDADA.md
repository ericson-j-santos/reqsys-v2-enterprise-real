# ReqSys — Referência Consolidada Canônica

Data de referência: 2026-06-20
Status: canônico
Escopo: ReqSys e frentes derivadas de requisitos, IA, integrações, analytics e governança.

## 1. Objetivo

O ReqSys deve operar como plataforma corporativa para captura, análise, refinamento, rastreabilidade e acompanhamento de requisitos, integrando IA, automações, backlog, documentação, painéis e governança de entrega.

## 2. Diretriz padrão ouro

Toda evolução deve considerar, no mínimo:

- Visão estratégica e aderência ao objetivo da solução.
- Engenharia de requisitos com itens atômicos, testáveis e rastreáveis.
- Modelagem de processos e fluxos ponta a ponta.
- Arquitetura documentada por ADRs.
- Backlog priorizado, roadmap e releases rastreáveis.
- Testes unitários, integração, contrato, segurança, acessibilidade e responsividade.
- CI/CD com quality gates e ambientes segregados.
- Observabilidade, auditoria, logs estruturados e `correlation_id`.
- Gestão de riscos, rollback e documentação operacional.

## 3. Requisitos canônicos

### 3.1 Funcionais

- Capturar demandas de múltiplas origens, incluindo canais manuais, integrações, formulários e agentes.
- Refinar demandas em requisitos claros, rastreáveis e testáveis.
- Gerar critérios de aceite em BDD/Gherkin quando aplicável.
- Manter backlog com prioridade, status, responsável, origem e histórico.
- Permitir análise executiva e analítica por cards, gráficos, tabelas e detalhes filtrados.
- Integrar com ferramentas externas somente por conectores governados e auditáveis.

### 3.2 Não funcionais

- Segurança por padrão, sem segredos versionados.
- Autenticação e autorização obrigatórias em fluxos sensíveis.
- Separação explícita de ambientes `dev`, `hml` e `prod`.
- Responsividade mobile-first e acessibilidade mínima WCAG AA quando aplicável.
- Logs estruturados sem PII ou segredos.
- Auditoria com `correlation_id` em operações relevantes.
- Falhas explícitas, rastreáveis e observáveis.

## 4. Arquitetura de referência

```text
Frontend Web / Painéis
        ↓
API / BFF / Gateway
        ↓
Camada de Aplicação
        ↓
Domínio / Regras de Negócio
        ↓
Portas e Adaptadores
        ↓
Bancos, filas, conectores, IA, BI e integrações externas
```

A arquitetura preferencial é modular, evoluindo para hexagonal quando houver domínio relevante, múltiplas integrações, necessidade de testes isolados e governança de longo prazo.

## 5. Governança de ambientes

| Ambiente | Finalidade | Regra |
| --- | --- | --- |
| `dev` | Desenvolvimento e experimentação controlada | Pode conter dados fictícios e mocks. |
| `hml` | Homologação funcional e técnica | Deve simular produção sem dados sensíveis reais. |
| `prod` | Operação real | Exige gates de segurança, CI verde, rollback e auditoria. |

## 6. Gates de produção

Produção deve ser bloqueada se ocorrer qualquer item abaixo:

- Autenticação desligada.
- CORS com `*`.
- JWT sem validação real de issuer/audience.
- Consulta com fonte sem retornar fontes.
- Consulta sem base gerando resposta inventada.
- Ingestão sem permissão administrativa.
- Logs com token, senha, CPF, PII ou connection string.
- Auditoria sem `correlation_id`.
- Connector admin exposto sem autorização.

## 7. Analytics e drill-down

Todo indicador relevante deve, quando fizer sentido, permitir navegação para analítico filtrado:

```text
card/gráfico/indicador → filtro contextual → visão analítica → item detalhado → origem/evidência
```

A UI deve priorizar componentes reutilizáveis, filtros preservados, URL compartilhável quando possível e rastreabilidade até a origem do dado.

## 8. Schema-Driven UI

Quando dados forem variáveis ou dependentes de integrações, adotar padrão `schema + data`:

- Backend retorna metadados dos campos.
- Frontend renderiza tabela, card, detalhe, filtros, ordenação, máscaras e permissões.
- Evita acoplamento rígido a nomes de colunas.
- Facilita evolução de integrações e painéis analíticos.

## 9. CI/CD e política de merge

Merge em `main` deve ocorrer somente após:

- PR com escopo claro.
- Branch atualizada ou compatível com `main`.
- CI completo concluído com sucesso.
- Evidências de teste informadas no PR.
- Risco e rollback documentados quando aplicável.

## 10. Documentação mínima por incremento

- Atualizar README quando afetar uso geral.
- Atualizar `docs/` quando afetar arquitetura, operação, segurança ou governança.
- Criar ou atualizar ADR quando houver decisão técnica relevante.
- Manter changelog/release note para entrega significativa.

## 11. Próximos incrementos recomendados

1. Consolidar PRs antigos e fechar duplicidades com justificativa.
2. Garantir CI verde antes de qualquer merge.
3. Completar painel de acompanhamento do ciclo completo.
4. Aplicar drill-down nas áreas analíticas já existentes.
5. Revalidar responsividade em todas as abas críticas.
6. Documentar matriz de rastreabilidade requisito → código → teste → release.
