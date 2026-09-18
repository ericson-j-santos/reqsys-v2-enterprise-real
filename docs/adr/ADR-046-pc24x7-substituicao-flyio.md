# ADR-046 — PC próprio 24x7 como substituto do Fly.io

Status: proposto (piloto restrito a dev iniciado em 2026-09-09 — ver
`docs/runbooks/pc24x7-piloto-dev.md`; comparação de custo inicial documentada
em 2026-09-10)
Data: 2026-09-09

## Contexto

Hoje o ReqSys roda três ambientes (dev, hml, prod) inteiramente no Fly.io, cada
um como app independente (`reqsys-api-dev`/`reqsys-app-dev`,
`reqsys-api-stg`/`reqsys-app-stg`, `reqsys-api`/`reqsys-app`), documentado em
`infra/fly-environments.json` e `docs/PADRAO_OURO_FLYIO_DUCKDNS.md`.

Levantamento de 2026-09-09 (ver histórico de PRs #1559/#1561) mostrou que esse
modelo já sofreu dois incidentes de crash loop no mesmo padrão de causa raiz
em menos de duas semanas, e que o deploy de produção depende de um gate manual
(workflow `deploy-production-sync.yml`, aprovação `APROVO-PROD`, referenciado
internamente como gate BACEN).

O usuário levantou a possibilidade de substituir o Fly.io por um computador
próprio ligado 24x7, motivado exclusivamente por **custo**. Não existe,
até esta data, nenhuma menção anterior a essa ideia no repositório (código,
histórico de commits em qualquer branch, issues ou PRs no GitHub) — esta é
uma proposta nova, sem discussão prévia para reaproveitar.

Decisões já tomadas pelo usuário para esta proposta:

- **Escopo:** os três ambientes (dev, hml e prod) migram do Fly.io para o PC 24x7.
- **Motivação:** custo (repetido duas vezes na resposta — é o único driver, não há preocupação declarada com controle de dados ou desconfiança do Fly.io).
- **Execução dos containers:** Docker/docker-compose, reaproveitando a stack
  local já existente e validada (`docker-compose.yml` + `docker-compose.dev.yml`,
  corrigida no PR #1557 para cobrir `JWT_ISSUER`/`JWT_AUDIENCE`).

## Respondendo as duas dúvidas técnicas que motivaram este ADR

**"Docker não daria?"** — Docker resolve *rodar* a aplicação (isso já
funciona hoje via `docker-compose.yml`, testado localmente). Docker **não**
resolve *tornar o PC acessível pela internet pública*. Um PC residencial
normalmente:
- não tem IP público fixo (o provedor pode trocar o IP a qualquer momento,
  ou usar CGNAT, que impede acesso externo mesmo com porta liberada no
  roteador);
- fica atrás de um roteador que bloqueia conexões de entrada por padrão.

Por isso a exposição pública é uma camada separada da execução dos
containers — são dois problemas distintos que este ADR trata em separado.

**"Cloudflare é gratuito 100% ou tem limitações?"** — O Cloudflare Tunnel
(`cloudflared`) é gratuito para este uso, sem limite de banda publicado, e é
a opção recomendada por não exigir abrir porta no roteador nem expor o IP
residencial (o túnel é sempre iniciado de dentro para fora). As limitações
reais não são de banda, são estas:

1. **Precisa de um domínio com DNS gerenciado pela Cloudflare.** Os domínios
   DuckDNS já usados hoje (`tieridev`/`tierin`/`tieriprod.duckdns.org`) **não
   servem diretamente** para isso — o Tunnel exige um registro `CNAME`
   apontando para `<tunnel-id>.cfargotunnel.com` dentro de uma zona DNS que a
   Cloudflare administra, e o DuckDNS não permite isso. É preciso um domínio
   próprio (pode ser um domínio barato, ~R$40–60/ano) com os nameservers
   apontando para a Cloudflare (o plano DNS da Cloudflare em si é gratuito).
2. **Sem SLA.** É um produto gratuito de melhor esforço — se a Cloudflare
   tiver uma instabilidade, não há suporte prioritário nem crédito de
   indisponibilidade.
3. **Depende inteiramente da energia e internet residencial.** Se faltar luz
   ou a internet cair, a aplicação cai — sem redundância.

## Decisão

Adotar, como proposta inicial (**ainda não implementada**, pendente das
decisões em aberto na seção seguinte):

1. Um único PC ligado 24x7 executa a stack via `docker-compose.yml` (o mesmo
   arquivo já usado localmente), com um `docker-compose.<ambiente>.yml` por
   ambiente (dev/hml/prod) definindo portas, variáveis e volumes distintos —
   análogo ao que hoje é feito com `fly.dev.toml`/`fly.staging.toml`/`fly.toml`.
2. Exposição pública via **Cloudflare Tunnel**, um túnel por ambiente,
   substituindo os domínios `*.fly.dev` e os atuais `*.duckdns.org`.
3. Um domínio próprio (a definir) tem seus nameservers migrados para a
   Cloudflare para permitir os registros CNAME dos túneis.
4. `backend/Dockerfile` (o mesmo Dockerfile único usado hoje pelo
   docker-compose) passa a ser também a imagem de produção — elimina de vez a
   necessidade de manter um Dockerfile específico de Fly.

## Riscos que precisam de decisão explícita antes de implementar

Este ADR fica em status **proposto**, não **aceito**, porque os itens abaixo
mudam a arquitetura de forma relevante e precisam de confirmação do usuário —
não é seguro implementar isso silenciosamente só porque a motivação de custo
foi confirmada.

1. **Ponto único de falha para os três ambientes ao mesmo tempo.** Hoje
   dev/hml/prod são três apps Fly independentes: um crash loop em dev (como
   os dois incidentes recentes) nunca derruba hml ou prod. Num único PC 24x7,
   uma falha de hardware, energia, internet residencial, ou até um `docker
   compose down` acidental, **derruba os três ambientes simultaneamente,
   incluindo produção**. Isso é uma regressão real de disponibilidade em
   troca de custo menor — precisa ser uma escolha consciente, não um efeito
   colateral não discutido.
2. **Gate de produção "BACEN" foi desenhado em torno do Fly.io.** O workflow
   `deploy-production-sync.yml` (aprovação manual `APROVO-PROD`) e o
   `infra/fly-environments.json` (`approval_required: true` para hml/prod)
   assumem deploy via `flyctl`. Migrar produção para o PC 24x7 exige redesenhar
   esse gate.

   **Investigado em 2026-09-09 (resolve o critério de aceite abaixo):** o
   "BACEN" não é um nome de convenção vazio — existe uma estrutura extensa e
   genuína em `governance/bacen/` (`CLOUD-THIRD-PARTY-REGISTER.yaml`,
   `CYBERSECURITY-POLICY.md`, `ACCESS-CONTROL-POLICY.md`,
   `INCIDENT-RESPONSE-PLAN.md`, `ANNUAL-CYBERSECURITY-REPORT.md`, etc.) e
   ~40 workflows `.github/workflows/bacen-*.yml` modelando controles reais de
   resoluções do Banco Central sobre nuvem/terceiros críticos, residência de
   dados, MFA, revisão de acesso e resposta a incidente.

   Porém `governance/bacen/CYBERSECURITY-POLICY-METADATA.yaml` e
   `governance/bacen/DEFERRED-INSTITUTIONAL-APPROVAL.md` deixam explícito que
   essa estrutura está em `lifecycle_stage: DEVELOPMENT`,
   `production_touched: false`, e que a aprovação institucional formal é
   **deliberadamente adiada** até uma eventual "institucionalização" — ou
   seja, o próprio sistema declara, por design, que ainda não representa uma
   instituição financeira real sob supervisão vigente do BACEN hoje. Não é
   fabricada evidência de conformidade; é uma prática/simulação de governança
   honesta sobre um produto ainda pré-oficialização.

   **Conclusão:** hospedar produção (no estágio atual, pré-institucional) num
   PC 24x7 **não viola nenhuma obrigação regulatória vigente hoje** — não há
   registro de que este sistema opere hoje como instituição financeira
   supervisionada de fato. Dito isso, o `CLOUD-THIRD-PARTY-REGISTER.yaml`
   também mostra que o próprio framework já antecipa provedores
   "self-hosted, conforme ambiente" (ex.: `BACEN-05-T12`/`T13`, Postgres e
   Redis) como categoria válida, então adicionar o PC 24x7 como um provider
   registrado (com `risk_review_status`/`dpa_status` preenchidos igual aos
   demais) é o caminho consistente com o padrão já usado no repositório — não
   precisa ser tratado como exceção.

   **Ressalva que continua de pé:** se este projeto algum dia avançar para
   `lifecycle_stage: PRODUCTION`/`INSTITUTIONAL` (uma instituição real
   supervisionada), as Resoluções BCB sobre computação em nuvem e serviços
   relevantes de processamento/armazenamento de dados (ex.: Resolução BCB
   nº 85/2021) exigem avaliação formal de risco, notificação e requisitos de
   segurança/continuidade que um PC residencial dificilmente atende (sem SLA,
   sem redundância geográfica, sem contrato formal de fornecedor). Migrar
   para o PC 24x7 agora, em fase de prática, é razoável; deixar de reverter
   essa decisão antes de uma eventual institucionalização real não seria.
3. **Sem plataforma gerenciada de restart/health.** Hoje a Fly Machines
   plataforma reinicia a máquina automaticamente em crash e expõe
   `auto_stop_machines`/`auto_start_machines`/health checks nativos. No PC
   24x7 isso precisa ser recriado localmente (ex.: `restart: unless-stopped`
   do próprio Docker já ajuda, mas não cobre queda de energia sem
   auto-start do Docker no boot do SO, nem alerta se o processo cair).
4. **Backup dos dados.** Hoje o Fly gerencia os volumes (`reqsys_data`,
   `reqsys_data_dev`, `reqsys_data_stg`). No PC 24x7, backup do banco
   (SQLite hoje em prod/dev/hml conforme `fly.toml`, ou Postgres se o
   docker-compose local for adotado) vira responsabilidade manual.
5. **Custo real não é zero.** Mesmo quando a fase 1 evita gasto novo, o custo
   econômico do piloto precisa ficar explícito: energia do PC ligado 24x7,
   tempo de administração, desgaste do hardware e, numa fase posterior,
   domínio próprio. A comparação inicial abaixo resolve a decisão de curto
   prazo: validar dev sem contratar nada novo.

## Comparação de custo inicial

Premissas de 2026-09-10 para decisão do piloto:

| Item | Fase 1: dev no PC 24x7 com Quick Tunnel | Fase 2: túnel nomeado com domínio | Manter Fly.io |
| --- | --- | --- | --- |
| Domínio | R$0 | ~R$40–60/ano | R$0, se usar somente `*.fly.dev` |
| Exposição pública | R$0 via Cloudflare Quick Tunnel | R$0 no plano Cloudflare Free, após domínio próprio | Incluso no Fly.io |
| Backup externo | R$0 usando Cloudflare R2 dentro do free tier + restic | Igual à fase 1 | Depende do volume/estratégia atual |
| Energia | Custo variável do PC ligado 24x7 | Igual à fase 1 | R$0 local |
| Administração | Manual: Docker, sistema operacional, backup, restauração e túnel | Manual, com DNS/túnel nomeado adicional | Parcialmente gerenciada pela plataforma |
| Disponibilidade | Sem SLA; depende de energia/internet residencial | Sem SLA local; URL estável melhora apenas o acesso | Plataforma gerenciada, com isolamento por app |

Conclusão operacional: **executar somente o piloto de dev na fase 1**, porque
ele não exige gasto novo e responde à restrição imediata de custo. O gasto com
domínio fica explicitamente adiado até a fase 2, depois que o piloto provar
estabilidade, backup restaurável e restart automático. Hml e prod permanecem
no Fly.io até decisão posterior baseada em evidência.

## Consequências

### Positivas

- Elimina o custo recorrente do Fly.io.
- Reaproveita a stack Docker já validada (PR #1557), sem trabalho de
  containerização do zero.
- Cloudflare Tunnel remove a necessidade de abrir portas no roteador ou expor
  o IP residencial — mais seguro que a alternativa de port-forward.

### Trade-offs

- Perde a redundância entre ambientes: um problema local agora pode afetar
  dev, hml e prod ao mesmo tempo.
- Perde a infraestrutura gerenciada da Fly (restart automático, volumes,
  observabilidade nativa da plataforma) — precisa ser recriada manualmente.
- Introduz dependência de energia/internet residencial para todos os
  ambientes, incluindo produção.
- Gate de produção atual (BACEN) precisa ser redesenhado; se o nome refletir
  um requisito regulatório real, produção pode não ser um bom candidato para
  hospedagem residencial.

## Critérios de aceite (para sair de "proposto" para "aceito")

- [x] Confirmado se o gate "BACEN" no deploy de produção reflete um requisito
      regulatório real ou é só um nome interno de convenção — **resolvido
      2026-09-09**: é uma prática de governança genuína, mas o próprio
      sistema declara `production_touched: false`/pré-institucionalização;
      não há bloqueio regulatório vigente hoje (ver seção de riscos acima).
- [x] Decisão explícita: produção realmente migra junto, ou fica no Fly.io
      enquanto dev/hml migram primeiro como piloto? — **resolvido
      2026-09-09**: usuário optou por **dev primeiro, isolado**. hml e prod
      continuam no Fly.io até o piloto ser validado (ver critério de saída em
      `docs/runbooks/pc24x7-piloto-dev.md`).
- [x] Estratégia de backup dos dados definida — **resolvido 2026-09-09**:
      reaproveita o padrão já usado pelo ReqSys para BACEN-04 (restic +
      Cloudflare R2, gratuito até 10 GiB), adaptado em
      `scripts/pc24x7_backup_restic.sh` para rodar no mesmo host (sem a
      orquestração de Fly Machines da versão original). Documentado em
      `docs/runbooks/pc24x7-piloto-dev.md`.
- [x] Estratégia de restart automático do PC/Docker após queda de energia ou
      reinício do sistema operacional definida — **resolvido 2026-09-09**:
      Linux com `systemctl enable docker` (recomendado para o PC 24x7
      definitivo); se continuar no Windows, WSL2 + Ubuntu + systemd + Docker
      Engine nativo (evita depender de login de usuário, ao contrário do
      Docker Desktop). Detalhes em `docs/runbooks/pc24x7-piloto-dev.md`.
- [x] Domínio definido e nameservers migrados para a Cloudflare — **resolvido
      2026-09-09 em duas fases**: fase 1 (agora, sem custo) usa Cloudflare
      Quick Tunnel — URL pública temporária, sem precisar de domínio próprio.
      Fase 2 (quando houver orçamento) troca para domínio próprio + túnel
      nomeado. Ver `docs/runbooks/pc24x7-piloto-dev.md`, seção 3.
- [x] Comparação de custo inicial (domínio + energia + tempo de administração)
      feita e documentada — **resolvido 2026-09-10**: fase 1 fica limitada a
      dev, Quick Tunnel e R2/free tier, sem contratação nova; domínio próprio
      é decisão de fase 2; hml/prod seguem no Fly.io até evidência do piloto.

## Próximo incremento

Piloto de **dev** iniciado em 2026-09-09 — ver
[`docs/runbooks/pc24x7-piloto-dev.md`](../runbooks/pc24x7-piloto-dev.md) para os passos
operacionais completos (subir a stack, expor via Cloudflare Quick Tunnel, configurar backup
restic/R2, garantir restart automático) e o critério de saída antes de revisitar hml/prod.
