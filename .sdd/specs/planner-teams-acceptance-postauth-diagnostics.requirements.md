# Planner → Teams DEV — Diagnóstico pós-autenticação

## Requisito 1 — falha sanitizada
Falhas após a autenticação devem ser classificadas por etapa sem persistir tokens, segredos ou respostas brutas.

## Requisito 2 — rastreabilidade operacional
Conexões, provisionamento, ativação, criação de tarefa e observação de execução devem possuir códigos estáveis quando falharem.

## Critérios de aceite (Acceptance Criteria)
1. Falhas de descoberta de conexões devem indicar `connections` com código sanitizado específico.
2. Falhas de implantação devem indicar `provisioning` sem conteúdo sensível.
3. Falhas posteriores de ativação, tarefa ou observação devem possuir etapa e código específicos.
4. O comportamento funcional do aceite DEV não deve ser alterado; apenas o diagnóstico persistido.
5. O teste contratual deve validar a presença dos códigos permitidos e o Pre-PR deve retornar `SDD_OK`.
