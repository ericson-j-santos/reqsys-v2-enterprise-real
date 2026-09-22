# Checklist de execução P0/P1 — ReqSys

## Estado atual

A execução foi validada com evidência real local:

- Backend `/health` respondeu 200 em http://127.0.0.1:8000/health
- Frontend respondeu 200 em http://127.0.0.1:5173/
- Smoke oficial do runtime passou para o ambiente local (`ok: 4 / total: 4`)
- Teste do pipeline de e-mail passou em backend (`6 passed`)

## P0 — origem real e gateway externo

### P0-01 — Confirmar DSN real do SQL Server e contrato das 4 views

Status: Bloqueado por ausência de configuração externa real

Critério de conclusão:

- [ ] Obter `MOVIMENTO_EMAIL_SOURCE_DSN` do ambiente real ou de teste
- [ ] Validar ao vivo os nomes reais das 4 views no SQL Server
- [ ] Atualizar os scripts SQL em `backend/app/services/movimento_email/sql/views/`
- [ ] Confirmar colunas e tipos contra `repository.py` e `models.py`
- [ ] Validar o fluxo com `jobs/executar` contra a origem real
- [ ] Registrar a evidência do contrato real em artifact operacional

Bloqueador confirmado:

- `MOVIMENTO_EMAIL_SOURCE_DSN` está ausente no ambiente atual
- Evidência capturada por `scripts/verificar_movimento_email_fontes.py status`

### P0-02 — Validar SMTP real para envio

Status: Ainda não executado; depende de credenciais reais

Critério de conclusão:

- [ ] Obter `MOVIMENTO_EMAIL_SMTP_HOST`, `PORT`, `USER`, `PASSWORD`, `FROM`
- [ ] Validar envio em `dry_run=true`
- [ ] Validar envio real controlado
- [ ] Confirmar que o e-mail sai com o payload correto
- [ ] Arquivar evidência de envio real

### P0-03 — Fechar a trilha de dados e produção

Status: Bloqueado por ausência do ambiente externo

Critério de conclusão:

- [ ] Contrato dos dados validado
- [ ] SMTP validado
- [ ] Readiness operacional confirmado
- [ ] Aprovadores/secret review concluídos
- [ ] Documento de promoção atualizado

## P1 — validação operacional e de jornada

### P1-01 — Smoke oficial do runtime

Status: Concluído localmente

- [x] `scripts/validate_public_runtime.py` executado com sucesso
- [x] Artefato gerado em `artifacts/public-runtime-local.json`
- [x] Artefato de readiness em `artifacts/public-readiness-local.json`

### P1-02 — Backend regressivo

Status: Concluído localmente

- [x] Testes do pipeline de e-mail executados e aprovados
- [x] `6 passed`

### P1-05 — Frontend build e suíte unitária em runtime compatível

Status: Concluído com Node 22

- [x] Build do frontend validada com Node 22 (`vite build`)
- [x] Suíte de testes unitários validada no runtime compatível (`260 passed`)
- [x] Evidência de incompatibilidade com Node 20 foi confirmada e isolada como ambiente, não como defeito do código

### P1-03 — Browser real da jornada principal

Status: Concluído localmente com evidência real

- [x] Frontend acessível em http://127.0.0.1:5173/
- [x] Evidência real capturada através do browser local
- [x] Artefato de evidência local existiu em `artifacts/real-evidence-local/`

### P1-04 — Rastreabilidade e governança de evidência

Status: Concluído para os itens críticos executados

- [x] Garantir que cada item crítico tenha artifact ou evidência de execução
- [x] Separar claramente qualidade técnica, publicação real e aceite do usuário
- [x] Registrar ações restantes em backlog governado

## Observação final

Este documento evita deixar etapas do P0/P1 em estado invisível ou esquecido. Os itens que dependem de ambiente externo continuam bloqueados, mas com critérios de término explícitos e sem ambiguidade.
