# Merge Readiness + Environment Promotion Gate

Data: 2026-07-09

## Problema corrigido

O workflow `merge-readiness.yml` condicionava o job principal ao resultado do router. Em pull requests draft, o job era ignorado e podia produzir percepção de execução sem jobs ou ausência do check obrigatório.

## Implementação

- Incluído evento `converted_to_draft`.
- Mantido o job `Merge readiness` sempre executável.
- Em PR draft, é gerado artifact `merge-readiness.json` com status `not_applicable`, decisão `skipped`, motivo auditável e correlation ID.
- Integrado o contrato de `Environment Promotion Readiness` ao merge gate.
- Publicadas evidências de merge e promoção no mesmo pacote de artifacts.
- Ampliados testes de contrato do workflow.

## Critérios de aceite

- Nenhum cenário suportado termina sem job executado.
- PR draft produz evidência explícita e não bloqueante.
- PR normal executa o Pareto Gate e o contrato DEV/STG/PROD.
- Artifacts permanecem disponíveis por 30 dias.
- Testes de workflow e promotion readiness permanecem verdes.

## Próximo incremento

Executar homologação DEV/STG/PROD com varredura visual e funcional por rota, evidência JSON e bloqueio de produção quando houver erro crítico de página, autenticação ou responsividade.
