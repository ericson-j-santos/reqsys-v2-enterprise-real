# Diagnóstico PMVS — Aula 1: Identificar (ID.AM / ID.RA)

> **Estado:** PARCIAL — diagnóstico documental, **não** homologação operacional ou conformidade certificada.  
> **Registro canônico para esta lacuna:** [issue #3156](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3156).  
> **Data de revisão:** 19/11/2026. **Ambiente analisado:** GitHub, somente leitura.  
> **ReqSys main inspecionada:** `a05e64bbc58a15314b42cfa9314f1d415535b05b`.  
> **Regras globais:** `chatgpt-operational-rules/main@58dcd4200f412a866278027ba9e433439a03f3b3`, v1.6.21.  
> `correlation_id=reqsys-pmvs-aula01-diagnostico-20261119` · `idempotency_key=reqsys:security:pmvs-aula1-identificar:2026-11-19`

## 1. Origem, escopo e limites

Síntese **autoral** dos requisitos de trabalho da Aula 1 (10/11/2026) do curso *Cibersegurança e Gestão de Riscos Digitais para Negócios*, combinada com inspeção de arquivos e issues **atuais** do ReqSys. Referenciais pedagógicos empregados: NIST CSF 2.0, funções **Identificar/ID.AM (ativos)** e **ID.RA (avaliação de riscos)**, com checklist **CIS Controls v8.1 IG1** e início do **Guia Interno de Uso de IA**.

**Não incluídos:** PDFs originais, slides, dados ou marcas d'água pessoais, reprodução extensa do material protegido, dados pessoais empresariais, segredos, prompts confidenciais ou suposta comprovação de incidente noticiado no curso. Manchetes são exemplos didáticos, **não** foram validadas como evidências atuais do produto.

**Método:** confirmar a existência de política/código/registro na `main`, separar essa existência de execução física e da efetividade nos ambientes e vincular pendências a registros canônicos preexistentes. Não foi realizado login no ReqSys, scan novo, restauração, teste de MFA, teste de IA, acesso a host ou deploy. O diagnóstico **não** permite inferir porcentagem global de conformidade.

## 2. O que já existe e o que falta

| Domínio / requisito de Aula 1 | Evidência existente na main ou issue | Estado comprovado nesta revisão | Lacuna / vínculo canônico |
| --- | --- | --- | --- |
| Política e responsabilidade pelo risco | `governance/bacen/CYBERSECURITY-POLICY.md`; `BACEN-CONTROL-MATRIX.yaml` | Política documentada; BACEN-01 **partial** | Aprovação institucional, sem criar outra política: [#1615](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1615) |
| Identidades, autorização e acesso privilegiado | `docs/PRODUCTION_SECURITY_GATES.md`, `governance/bacen/ACCESS-CONTROL-POLICY.md`; BACEN-02 **partial** | Gates de configuração documentados (JWT, CORS, login demo), sem E2E vigente nesta avaliação | Evidência de MFA e revisão de acessos: [#1615](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1615) |
| Engenharia segura, secrets, logs | `docs/security/SECURITY_BASELINE.md`; `docs/ai-governance/00_PRIORITY_RULES.md`; BACEN-06 **implemented** no catálogo | Baseline automatizado **declarado em documentos**, não scan atualizado nem aprovação de produção | Reconfirmar logs/CI no SHA alvo; vulnerabilidade específica já rastreada em [#3136](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3136) |
| Resposta a incidentes | `governance/bacen/INCIDENT-RESPONSE-PLAN.md`; BACEN-03 **implemented** no catálogo com exercício automatizado | Plano e cenário registrados; operação real/humana não verificada aqui | Validar exercícios e métricas reais no controle BACEN-03 existente |
| Backup, recuperação e continuidade | `governance/bacen/BACKUP-RESTORE-POLICY.md`; [#1156](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1156) | Exercício **isolado** reportado como aprovado em 07/10; não comprova cobertura dos ativos DEV/STG/PROD | [#1162](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1162) atualizada 18/11: **armazenamento externo=false**; `rollout_pending` em três ambientes |
| Terceiros e fornecedores | `governance/bacen/CLOUD-THIRD-PARTY-REGISTER.yaml`; BACEN-05 **partial** | Lista de fornecedores registrada, porém não equivale a avaliação/contrato aprovado | DPA, revisão de risco e decisão institucional: [#1615](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1615) |
| Trilha e retenção | `governance/bacen/AUDIT-EVIDENCE-RETENTION-POLICY.md`; BACEN-07 **implemented** no catálogo | Contrato documental existente | Testar integridade, retenção e rastreabilidade do processo-alvo em execução real |
| Administração de riscos e decisão | BACEN-08 **partial**; matriz e relatório anual em `governance/bacen/` | Artefatos de governança presentes | Designação/assinatura formal: [#1615](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1615) |
| Identificação dos **5–8 ativos críticos** (ID.AM) | [#3149](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3149) cataloga sites, módulos e acessos | Catálogo de aplicações **não substitui** inventário de ativos, donos e tolerância à parada | **Novo recorte necessário** nesta [#3156](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3156), reutilizando dados da #3149 |
| Riscos por ativo, probabilidade e impacto (ID.RA) | Controles especializados existentes | **Não identificado diagnóstico unificado** no formato da aula nas buscas pontuais efetuadas | Preencher matriz e top 3 nesta #3156; sem inventar pontuação |
| Inventário de uso de IA na organização | `docs/ai-governance/` com regras; [#3151](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3151) trata validação física de Ollama/RAG | Diretrizes presentes, sem comprovação de inventário de uso real por área | Levantamento do uso real nesta #3156; testes do Ollama continuam na #3151 |

**Leitura correta dos estados:** `implemented`/ `partial` são valores observados **na matriz de controles**, não notas emitidas por esta auditoria. Não classificar um controle como efetivo somente por existir YAML, CI, teste em ambiente isolado ou issue verde.

## 3. Inventário inicial de candidatos a ativos críticos — ID.AM

O material da aula pede **5 a 8 ativos**, incluindo dados, sistemas, pessoas, fornecedores, dinheiro e reputação. Os itens abaixo são **candidatos para validação**, não um inventário homologado.

| Candidato | Tipo | Impacto potencial a verificar | Proprietário | Tolerância máxima sem ativo |
| --- | --- | --- | --- | --- |
| Dados e armazenamento operacional do ReqSys | Dados / sistema | Parada, perda, exposição, inconsistência | **A confirmar** | **A medir** |
| Identidade corporativa e autorização (Entra/MSAL) | Identidade | Bloqueio indevido ou acesso não autorizado | **A confirmar** | **A medir** |
| Código e cadeia GitHub/CI de entrega | Sistema / fornecedor | Alteração insegura ou indisponibilidade de entrega | **A confirmar** | **A medir** |
| Hosts e Runtime Platform governados | Equipamento / serviço | Interrupção de jobs, falha de retomada | **A confirmar** | **A medir** |
| Integrações Teams, Planner, Power Platform e filas | Sistema / fornecedor | Falha na comunicação e no fluxo de negócio | **A confirmar** | **A medir** |
| Backups, material de restauração e evidências críticas | Dados / continuidade | Perda de recuperabilidade | **A confirmar** | **A medir** |
| Cofre/segredos e identidades de serviço | Credenciais / segurança | Comprometimento privilegiado ou paralisação | **A confirmar** | **A medir** |
| IA local Ollama/RAG e dados de contexto | Modelo / sistema / dados | Uso indevido de dados, saída não confiável, indisponibilidade da automação | **A confirmar** | **A medir** |

Para cada ativo efetivamente selecionado, registrar: `asset_id`, ambiente, valor para o negócio, classificação do dado, dependências, dono, impacto em confidencialidade/integridade/disponibilidade, `RPO`, `RTO`, tempo máximo tolerável, evidência/fonte, data de revisão e responsável pela validação. **Não** cadastrar contas, senhas, CPFs ou conteúdo de clientes.

## 4. Método do mapa de riscos — ID.RA

A Aula 1 utiliza **probabilidade P (1 a 3)** e **impacto I (1 a 3)**. `nota=P×I`; o julgamento deve ser **documentado**, nunca inferido do nome de um ativo.

- **P=1:** não ocorreu na organização nem no setor; **P=2:** ocorreu no setor ou quase ocorreu internamente; **P=3:** ocorreu internamente ou é frequente no setor.
- **I=1:** resolvido em horas sem cliente afetado; **I=2:** dias de transtorno e alguns clientes afetados; **I=3:** operação parada, dados expostos, caixa ou reputação em risco.
- **Leitura contextual:** 1 aceitar *somente com decisão formal*; 2 monitorar; 3 = contingência se P1/I3 ou rotina se P3/I1; 4 planejar; 6 prioridade; 9 agir agora.
- **Tratamento:** reduzir, transferir, evitar ou aceitar (aceitação registrada pelo dono; transferência financeira não transfere responsabilidades legais).

| Cenário a analisar (hipótese, não incidente confirmado) | Vinculação | P | I | Nota | Próximo passo |
| --- | --- | --- | --- | --- | --- |
| Backup do dado crítico não recuperável em incidente real | #1162 | Não avaliada | Não avaliado | **Pendente** | Verificar armazenamento, restauração, integridade, RPO/RTO |
| Acesso privilegiado indevido ou sem revisão formal | #1615 | Não avaliada | Não avaliado | **Pendente** | Validar MFA, desligamentos e revisão de privilégios |
| Exposição de dados em IA não aprovada | #3156 / #3151 | Não avaliada | Não avaliado | **Pendente** | Inventariar aplicações de IA e classificação de dados |
| Interrupção por terceiro crítico | #1615 | Não avaliada | Não avaliado | **Pendente** | Verificar dependência, contrato, contingência |
| Vulnerabilidade de dependência explorável | #3136 | Não avaliada | Não avaliado | **Pendente** | Conferir correção e resultado do scanner atualizado |

**Top 3:** não definido sem dados e donos. Escolher os três maiores `P×I` **somente após avaliação**; documentar responsável, ação em até 30 dias, vencimento e tratamento. Empates devem registrar justificativa da decisão.

## 5. Checklist CIS Controls v8.1 IG1 — recorte da aula

| Controle | Evidência a apresentar para marcar 'Tem' | Situação da avaliação |
| --- | --- | --- |
| **1.1** Inventário de dispositivos | Inventário atual verificável: PCs, celulares, servidores, rede | **Não verificado especificamente** |
| **1.2** Ativos não autorizados | Registro de identificação, isolamento ou regularização | **Não verificado especificamente** |
| **2.1** Inventário de software/serviços | Lista atual com versões e proprietários | **Não verificado especificamente** |
| **2.2** Software suportado | Prova de suporte ou exceção aprovada | **Não verificado especificamente** |
| **2.3** Software não autorizado | Evidência de remoção, quarentena ou regularização | **Não verificado especificamente** |
| **3.1** Gestão do ciclo de dados | Proprietário, local, prazo de retenção e descarte | **Não verificado especificamente** |
| **3.2** Inventário de dados relevantes | Mapa de dados sensíveis e localização abstrata, sem conteúdo | **Não verificado especificamente** |

Preenchimento válido: `Tem / Parcial / Não tem / Não sei`, evidência, dono e data. 'Não sei' é pendência de verificação, **não** equivale a 'Não tem'. Reaproveitar catálogos e controles existentes, sem desenvolver um segundo inventariador por conveniência.

## 6. Inventário e regra provisória de uso de IA

**Regra provisória:** não inserir dados pessoais de clientes/funcionários nem informações confidenciais em IA não aprovada; preferir contas corporativas onde houver política e autorização. A regra definitiva depende de aprovação formal, classificação de dados e base LGPD.

Levantar por **ferramenta/instância** (inclusive IA embutida em editor, CRM, e-mail, transcrição, automação, Ollama/RAG):

`ferramenta | area | finalidade | aprovada? | classe do dado | recebe PII/sigilo? | destino/processador | responsavel | evidência`.

Sem preenchimento presumido: **nenhuma ferramenta automaticamente considerada aprovada** por constar na arquitetura. O funcionamento físico de Ollama deve ser tratado **somente na issue #3151**.

## 7. Plano Pareto — 30 dias, sem criar soluções paralelas

Os prazos são **metas de planejamento relativas ao aceite**, não promessas de execução e não autorizam tocar produção. Em todos os casos, custo adicional **R$ 0,00** ou **bloqueio** diante de incerteza.

| Prioridade | Trabalho mínimo | Dono funcional | Registro oficial | Aceite objetivo | Meta |
| --- | --- | --- | --- | --- | --- |
| P0-A | Confirmar 5–8 ativos e seus donos, criticidade, tempo tolerável e dependências; aproveitar catálogo existente | BUSINESS OWNER + SECURITY | **#3156**; reutilizar #3149 | Inventário assinado e fontes por ativo | D+7 |
| P0-B | Remover a ausência de evidência de backup externo e restauração por ativo/ambiente **sem criar serviço novo nem gasto** | RUNTIME_OPERATOR + SECURITY | **#1162** | Backup externo cifrado e restauração isolada real com SHA/digest, integridade, RPO/RTO, ambiente e dono; DEV→STG e PROD somente com gates/autorizações próprios | D+14 para diagnóstico e desbloqueio seguro; conclusão condicionada |
| P0-C | Formalizar prova de MFA e revisar privilégios/contas de terceiros | SECURITY + gestor de identidades | **#1615** | Evidência autenticada, revisão assinada, exceções rastreadas; sem captura de credenciais | D+14 |
| P1-A | Preencher checklist CIS 1.1/1.2/2.1/2.2/2.3/3.1/3.2 a partir de registros existentes | SECURITY + RUNTIME_OPERATOR | **#3156** | Sete linhas com 'Tem/Parcial/Não tem/Não sei', evidência, dono e prazo | D+14 |
| P1-B | Levantar ferramentas de IA e tratamento de dados por área; validar política provisória | AI_GOVERNOR + DPO/SECURITY | **#3156**; prova física em #3151 | Inventário real validado, aprovação/PII/tratamento explicitados, sem compartilhar prompts sigilosos | D+21 |
| P1-C | Conferir fornecedores críticos e responsabilidades contratuais | GOVERNANCE + jurídico | **#1615** | DPA/risco/continuidade validados onde aplicáveis, ou bloqueio explícito | D+21 |
| P1-D | Atribuir P e I, aprovar top 3 e registrar ações de 30 dias | BUSINESS OWNER + SECURITY | **#3156** | 3 riscos com `P×I`, evidência, dono, data, tratamento e decisão, inclusive aceitação formal se houver | D+30 |
| P2 | Validar exercício de resposta e leitura independente de execução | SECURITY + RUNTIME_OPERATOR | Controle BACEN-03 existente | Teste documentado de papéis, alerta, contenção, recuperação e lições; sem simular incidente real | Após P0 |

**Dependências:** o top 3 depende de identificação e coleta confiável; a ativação de backup real depende de atestar custo zero/quotas e autorização de ambiente; conclusão institucional não pode ser automatizada por inferência. Esta documentação **não** encerra #1162, #1615 ou #3151.

## 8. Governança, riscos e próxima ação

- **Classificação desta alteração:** documentação/diagnóstico autoral, sem novos controles executáveis; **não** é reparo de falha em runtime nem funcionalidade implantada.
- **Publicação:** branch isolada de `main@a05e64bbc58a15314b42cfa9314f1d415535b05b`. Não modificar `main`, merges, deploys, secrets, permissões ou hosts nesta entrega.
- **READY_FOR_PR:** deve ser comprovado em SHA vigente pelo *Pre-PR Readiness Gate* do ReqSys **antes de abrir PR**. Sem esse resultado, manter somente branch e issue. PR não é autorizado por documentação publicada.
- **TODO Global:** sincronização **pendente**, sem confirmação de evento consumido. `event_id` novo só deve existir quando o produtor canônico realmente emitir e receber recibo. `idempotency_key` acima deve permanecer estável.
- **Teste desta fase:** consistência de IDs, links de issues, não exposição de dados, presença dos critérios da aula e leitura independente do blob Git remoto. **Não há E2E operacional.**
- **Próxima ação de maior valor:** o responsável pelo produto e SECURITY validarem o inventário de 5–8 ativos na #3156; paralelamente, RUNTIME_OPERATOR retomar a #1162 sem duplicação e provar ou bloquear a capacidade real de recuperação com custo adicional nulo.

**Estado de aceite do PMVS:** `PARCIAL`. **Percentual:** não mensurável enquanto ativos/riscos e aceites não estiverem preenchidos. **Prazo final:** não estimável sem pré-condições e dados reais.
