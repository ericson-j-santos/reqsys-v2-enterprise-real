# ReqSys Low-Code - Canvas da Solution

## Visao geral

Solution: `ReqSysLowCode`  
Ambiente alvo: `dev`  
Modo: `dry_run_blueprint` \*\*\*\*
Status: `planned`

## Canvas App

App: `ReqSysLowCode Canvas App`  
Tela inicial: `scrDashboard`  
Layout: `responsive_tablet`

| Tela          | Objetivo                                                        | Componentes                                                            |
| ------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Painel ReqSys | Resumo operacional com demandas, aprovacoes, riscos e releases. | Header, KpiStrip, DemandasRecentes, AprovacoesPendentes, ReleaseStatus |
| Demandas      | Criar, classificar e acompanhar demandas.                       | DemandForm, DemandGallery, PriorityBadge, SubmitForApprovalButton      |
| Requisitos    | Detalhar requisitos, regras e criterios de aceite.              | RequirementForm, AcceptanceCriteriaEditor, TraceabilityPanel           |
| Aprovacoes    | Decidir aprovacao, rejeicao ou devolucao para ajuste.           | ApprovalQueue, DecisionPanel, AuditTimeline                            |
| Evidencias    | Registrar evidencias de qualidade, operacao e release.          | EvidenceUpload, EvidenceGallery, ReleaseLink                           |

## Dataverse

| Tabela     | Logical name       | Colunas |
| ---------- | ------------------ | ------: |
| Demandas   | `reqsys_demanda`   |       8 |
| Requisitos | `reqsys_requisito` |       8 |
| Aprovacoes | `reqsys_aprovacao` |       8 |
| Evidencias | `reqsys_evidencia` |       8 |
| Releases   | `reqsys_release`   |       8 |

## Power Automate

| Flow                            | Trigger                                      | Acoes                                                                 |
| ------------------------------- | -------------------------------------------- | --------------------------------------------------------------------- |
| ReqSys - Intake de demanda      | Dataverse: row added on Demandas             | Calcular prioridade, Criar aprovacao inicial, Notificar Teams         |
| ReqSys - Aprovacao de requisito | Dataverse: status em_aprovacao on Requisitos | Start and wait for approval, Atualizar requisito, Registrar evidencia |
| ReqSys - Release governance     | Manual button or scheduled                   | Consolidar evidencias, Gerar go/no-go, Notificar stakeholders         |
| ReqSys - Copilot handoff        | Copilot Studio action                        | Criar demanda, Vincular contexto, Retornar numero da demanda          |

## Copilot Studio

Agente: `ReqSysLowCode Copilot`  
Topicos: Criar demanda, Consultar status, Preparar aprovacao, Resumo de release

## Security roles

ReqSys Solicitante, ReqSys Aprovador, ReqSys Administrador Low-Code, ReqSys Auditor
