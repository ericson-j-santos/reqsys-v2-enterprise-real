# Runbook — Qualidade IA baixa e replicação anonimizada entre ambientes

## Diagnóstico: por que o score de Qualidade IA está baixo em todos os ambientes

O score (`GET /v1/qualidade-ia/resumo`, implementado em `backend/app/services/ai_quality.py`)
é calculado **ao vivo a partir de dados reais** de cada ambiente — não é um valor configurável
nem pode ser mascarado (`ai_quality.py`, mensagem do `guardrail_100`: *"Não mascarar o score;
tratar gaps antes de considerar o guard rail aprovado"*).

Fórmula resumida:

| Métrica | Depende de |
|---|---|
| `acuracia` / `relevancia` | % de requisitos com status em `STATUS_APROVADOS`/`STATUS_EM_ANALISE` (`app/services/requisitos_metricas.py`) |
| `consistencia` | % de requisitos **fora** dessas categorias (bucket "pendente") |
| `seguranca` | incidentes críticos nos últimos 7 dias (auditoria com `erro`/`falha`/`incidente`/`vulnerabilidade`) |
| `cobertura_dados` | % de requisitos com `descricao` ≥ 40 caracteres |

Validado em 2026-07-03: os 3 ambientes têm amostra muito pequena (prod=5, dev=1, hml=0
requisitos) e, em prod/dev, **100% dos requisitos estão em `status=backlog`**, que não cai em
nenhuma categoria reconhecida (`aprovado`/`em_analise`/`rejeitado`) — logo contam como
"pendente" e derrubam `acuracia`, `relevancia` e `consistencia`.

**Isso não é um bug de código.** É a consequência honesta de (a) amostra pequena e (b)
requisitos que nunca foram triados até um status reconhecido. A correção real é uma decisão
de produto/negócio (triar os requisitos existentes) — não algo que deva ser automatizado
silenciosamente.

### Ferramenta de diagnóstico

```bash
python scripts/relatorio_qualidade_ia_pendentes.py
```

Lista, por ambiente, quais requisitos estão pendentes de triagem. Somente leitura.

### Snapshot de tendência

`.github/workflows/qualidade-ia-snapshot.yml` roda diariamente (03:20 UTC) e sob demanda,
chamando `POST /v1/qualidade-ia/snapshot` em prod/hml/dev via `scripts/registrar_qualidade_ia_snapshot_ci.py`,
publicando o `score_geral` no resumo do workflow e emitindo `::warning` quando `score_geral < 70`.
O histórico fica disponível em `GET /v1/qualidade-ia/tendencia` (por ambiente).

## Replicação anonimizada de requisitos (prod → hml/dev)

Com amostra tão pequena, testar filtros, triagem e o próprio score em hml/dev é pouco
representativo. `scripts/replicate_requisitos_anonimizado.py` copia os requisitos de produção
para hml/dev preservando conteúdo de produto (`titulo`, `descricao`, `area`, `sistema`,
`urgencia`, `impacto_regulatorio`) e **mascarando `solicitante`** com um pseudônimo estável
derivado de hash (nunca o nome/e-mail original) — atendendo ADR-002 (LGPD).

Escopo deliberado:

- **Replica**: `requisitos` (via `GET/POST /v1/requisitos`, endpoints públicos hoje).
- **Não replica**: `auditoria` nem `recommendation_ia`. A trilha de auditoria de cada
  ambiente deve refletir só eventos reais daquele ambiente (ADR-003); fabricar eventos de
  auditoria em hml/dev a partir de produção contaminaria a evidência operacional local.
- **Idempotente**: cada requisito replicado carrega uma marca `[origem-replicacao-anonimizada: REQ-xxxx]`
  no fim da `descricao`; reexecuções pulam o que já foi replicado.
- **Status não é copiado como aprovado**: todo requisito novo nasce em `recebido` (padrão do
  modelo) — a replicação não infla o score, só amplia a amostra para triagem real.

### Uso

```bash
# Dry-run (padrão) — só mostra o que faria, não grava nada
python scripts/replicate_requisitos_anonimizado.py

# Aplicar de fato em hml + dev
python scripts/replicate_requisitos_anonimizado.py --execute

# Escopo customizado
python scripts/replicate_requisitos_anonimizado.py \
  --source https://reqsys-api.fly.dev \
  --target https://reqsys-api-stg.fly.dev \
  --execute
```

Execução manual (`workflow_dispatch` ou local) — deliberadamente **não agendado**, porque
mesmo anonimizado ele grava em ambientes vivos e deve ser uma decisão consciente.

## Achado de segurança correlato (fora do escopo deste runbook)

`GET/POST /v1/requisitos` não exige autenticação em nenhum ambiente hoje — inclusive o campo
`solicitante` (frequentemente um e-mail pessoal) fica publicamente legível em produção sem
token. Isso já é uma exposição de dado pessoal via endpoint público, independente da
replicação descrita aqui. Recomenda-se tratar como item separado de RBAC (ADR-004), não
como parte desta automação.
