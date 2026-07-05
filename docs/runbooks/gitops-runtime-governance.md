# GitOps Runtime Governance

## Decisão

GitOps no ReqSys não deve ser tratado apenas como deploy automatizado. A referência operacional passa a ser **governança de mudança conectada à execução real**.

O Git continua sendo a fonte declarativa da intenção, mas a mudança só é considerada concluída quando houver evidência de que foi:

1. aprovada por PR;
2. versionada no Git;
3. aplicada no ambiente alvo;
4. observada no runtime;
5. validada com critérios pós-deploy;
6. acompanhada de capacidade de recuperação.

## Problema extraído

A prática comum `YAML no Git + PR + ArgoCD sincronizando` cria somente uma sensação de controle quando não existe evidência runtime.

Riscos escondidos:

- o controller sincroniza, mas a carga pode não subir corretamente;
- o pod ou serviço pode parecer saudável, mas entrar em falha silenciosa;
- o rollback pode existir, mas a recuperação pode nunca ter sido testada;
- o PR pode ser aprovado, mas gerar incidente ou nenhum valor mensurável;
- a falha de sincronização pode ser tratada tarde demais, sem diagnóstico objetivo.

## Cadeia governada obrigatória

| Camada | Pergunta de controle | Evidência esperada | Estado alvo |
| --- | --- | --- | --- |
| Intenção | O PR descreve o motivo, risco e impacto? | PR, issue, ADR ou changelog com escopo claro | Verde |
| Mudança | O Git contém alteração rastreável e reversível? | commit, diff, versão, contrato ou manifesto | Verde |
| Execução | A mudança foi aplicada no ambiente correto? | evento de deploy/sync, ambiente, versão e correlation_id | Verde |
| Observabilidade | O runtime confirmou saúde e comportamento esperado? | métricas, logs, traces, probes e smoke tests | Verde |
| Recuperação | Existe rollback validado ou plano de reversão testável? | runbook, comando, evidência ou simulação | Verde |

## Definição de pronto

Uma mudança GitOps só pode ser considerada **concluída** quando atender aos critérios abaixo:

- CI obrigatório verde ou justificativa explícita de exceção controlada;
- PR aprovado com escopo, risco e rollback documentados;
- ambiente alvo identificado;
- artefato de execução ou sincronização registrado;
- smoke test ou health check executado após deploy;
- evidência de logs/métricas/traces vinculada à mudança;
- rollback, restore ou plano de recuperação registrado;
- changelog atualizado quando houver alteração funcional, operacional ou de contrato.

## Mudança de linguagem operacional

Antes:

> O pull request foi mesclado.

Depois:

> A mudança foi aprovada, aplicada, observada e validada no ambiente alvo.

## Aplicação no ReqSys

Para o ReqSys, esta diretriz deve ser aplicada especialmente em:

- PRs com impacto em backend, frontend, banco, infraestrutura, workflows, contratos OpenAPI, integrações, automações e agentes;
- deploys em Fly.io, GitHub Pages, ambientes Docker e pipelines CI/CD;
- mudanças em rotas críticas, autenticação, providers LLM, orquestradores, ADRs, dashboards executivos e rotinas operacionais;
- incrementos contínuos onde o merge isolado não comprova valor de produção.

## Sinalização executiva

| Cor | Condição | Ação |
| --- | --- | --- |
| Verde | Aprovado, aplicado, observado e recuperável | Consolidar e seguir próximo incremento |
| Amarelo | Aprovado/aplicado, mas sem evidência runtime completa | Complementar evidência antes de expandir |
| Vermelho | CI falhou, sync falhou, saúde degradada ou rollback ausente | Bloquear continuação funcional e corrigir |

## Checklist operacional

- [ ] PR possui objetivo, escopo, impacto, rollback e plano de teste.
- [ ] CI obrigatório está verde.
- [ ] Mudança está associada a ambiente alvo.
- [ ] Existe evidência de execução/sincronização.
- [ ] Existe evidência de saúde pós-deploy.
- [ ] Logs/métricas/traces permitem diagnóstico por correlation_id, versão ou commit.
- [ ] Rollback ou recuperação está documentado.
- [ ] Resultado foi classificado como valor, neutro ou incidente.

## Limites

Esta diretriz não autoriza deploy automático em produção, alteração destrutiva de banco, execução contra ambiente corporativo sensível ou bypass de CI. Exceções devem ser registradas com justificativa, aprovador e plano de reversão.
