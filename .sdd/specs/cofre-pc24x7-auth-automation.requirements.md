# Cofre PC24x7 — automação de credenciais de evidência

## Objetivo
Automatizar o uso governado das credenciais necessárias ao ciclo de evidência do Cofre em DEV PC24x7, mantendo autenticação humana real quando exigida e impedindo exposição de segredos.

## Requisitos
1. O JWT administrativo deve ser obtido de autenticação real ou de leitor do Cofre limitado a `human_admin_jwt:dev`; não pode ser fabricado nem publicado.
2. Após captura de JWT válido, o fluxo deve criar automaticamente o leitor escopado e persistir somente esse token local restrito.
3. O executor deve conseguir recuperar o JWT pelo leitor escopado sem colocá-lo na linha de comando, stdout, stderr, Git ou evidência pública.
4. A chave Fernet do estado deve ser gerada de forma efêmera no `before-restart`, reutilizada no `after-restart` e removida após conclusão bem-sucedida.
5. A origem do frontend PC24x7 deve ser informável explicitamente, sem depender dos padrões legados Fly.io.
6. O escopo deste incremento é DEV; produção não deve ser alterada.

## Critérios de aceite
1. Os testes específicos de automação do Cofre passam no SHA exato da branch.
2. A regressão existente de `cofre_runtime_evidence.py` permanece verde.
3. Um caso negativo prova falha fechada quando a chave Fernet necessária ao `after-restart` não existe.
4. Repetir os testes não cria alteração de estado no repositório.
5. O Pre-PR Readiness termina `passed`, com `behind_by=0`, SDD válido e sem bloqueadores.
6. Nenhum JWT, chave Fernet ou token do Cofre aparece em evidência pública.
