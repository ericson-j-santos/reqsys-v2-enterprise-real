# Evidência pública pós-merge e produção consolidada

## Decisão executiva recomendada

Este ciclo deve priorizar a conclusão auditável da cadeia `evidência → produção consolidada` antes de iniciar novos incrementos funcionais ou novas camadas paralelas de governança.

## Prioridades aprovadas

1. **Priorizar evidência pública pós-merge.** O commit integrado à `main` só deve ser tratado como estabilizado quando houver evidência pública, rastreável e vinculada ao SHA validado.
2. **Consolidar artifact operacional recente.** A leitura executiva deve usar o artifact operacional mais recente como fonte canônica temporária, evitando duplicidade de relatórios concorrentes.
3. **Fechar o ciclo `evidência → produção consolidada`.** Antes de expandir funcionalidade, confirmar que a evidência pós-merge, a saúde operacional e a validação de produção estão conectadas em uma narrativa única.
4. **Evitar múltiplos incrementos paralelos de governança.** Novas automações de governança devem ser pausadas até que a evidência operacional atual esteja consolidada e publicamente verificável.

## Critério de pronto deste ciclo

O ciclo só deve ser considerado pronto quando todos os itens abaixo estiverem satisfeitos:

- workflow pós-merge executado para o SHA-alvo da `main`;
- artifact operacional recente publicado e identificável;
- evidência pública referenciada em resumo executivo, runbook ou artifact consumível;
- ausência de novo incremento paralelo de governança sem justificativa formal;
- decisão de avanço funcional registrada após a consolidação da evidência.

## Fora de escopo imediato

- Criar novos dashboards executivos.
- Adicionar novos gates obrigatórios de branch protection.
- Expandir automações autônomas de governança.
- Alterar deploy, runtime ou regras de produção.

## Operação recomendada

1. Executar ou aguardar o workflow pós-merge aplicável ao SHA da `main`.
2. Validar o artifact operacional mais recente publicado pelo workflow.
3. Registrar a evidência pública no canal operacional definido.
4. Somente depois disso, reabrir priorização para expansão funcional.

## Risco de não seguir a decisão

Executar novos incrementos paralelos de governança antes de consolidar a evidência aumenta o risco de falso senso de controle, múltiplas fontes de verdade e dificuldade de auditoria do estado real de produção.
