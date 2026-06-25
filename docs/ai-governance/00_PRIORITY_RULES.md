# Priority Rules

Codigo: AI-GOV-PRIORITY-001

Regras maximas para uso da IA em projetos corporativos.

## Prioridade P0

Regras P0 bloqueiam merge, release ou producao quando violadas.

## Sempre aplicar

- Padrao ouro.
- Seguranca por padrao.
- LGPD e minimizacao de dados.
- Rastreabilidade ponta a ponta.
- Ambientes segregados.
- CI/CD como gate obrigatorio.
- Documentacao viva.
- Arquitetura viva.
- Analytics e drill-down quando fizer sentido.
- Testes automatizados.
- Decisoes registradas em ADR.

## Bloqueios de producao

Bloquear publicacao quando houver:

- Auth desabilitada.
- JWT sem validacao real.
- CORS aberto sem restricao.
- Logs com segredo, token, CPF, PII ou connection string.
- CI falhando.
- Consulta sem fonte rastreavel.
- Auditoria sem correlation_id.

## Referencia cruzada

- ReqSys: aplicar em PRs, releases e validacoes.
- AI Governance dedicado futuro: manter este arquivo como regra raiz.
