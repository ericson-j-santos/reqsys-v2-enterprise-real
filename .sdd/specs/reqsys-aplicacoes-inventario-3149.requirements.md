# Catálogo de aplicações e sites do ReqSys — issue #3149

## Problema
Várias interfaces ReqSys/contratos foram criadas e publicadas separadamente; não existe, comprovadamente, uma visão única no produto original que indique código, acesso, estado, duplicação e uso real. Não substituir a aplicação existente nem declarar funcionamento a partir de publicação.

## Tipo e origem
- `feature` complementar ao Painel de Projetos existente: inclusão de inventário de aplicações (a rota de projetos já existe, não é reparo).
- Fonte: issue #3149 criada antes do início da branch. Autoria assistida, `source_mode=assisted`, `model_calls=0`; não alegar Builder/Validator independente.
- Base: `main@a05e64bbc58a15314b42cfa9314f1d415535b05b`; regras `main@58dcd4200f412a866278027ba9e433439a03f3b3`.
- Escopo limitado ao frontend: dados estáticos classificados, componente de leitura e inclusão em `/painel-projetos` (permissão `dashboard:read` existente).

## Requisitos
1. O catálogo exibe ID único, nome, fonte/caminho Git, SHA observado (sem confundir com SHA implantado), URL externa quando conhecida, versão AppDeploy, estado, acesso, responsável e próxima ação.
2. Deve marcar toda aplicação sem E2E como **não comprovada**. Publicação no AppDeploy ou código no repositório não certificam operação em servidor, login, integração, recuperação física ou continuidade.
3. A leitura não pode realizar login externo, buscar credenciais ou disparar execução, deploy, merge, alteração de permissões ou chamada de backend.
4. Links externos devem usar HTTPS, `target="_blank"` e `rel="noopener noreferrer"`; navegação não deve vazar tokens.
5. A busca filtra registros por texto e apresenta estado vazio; não altera nem sincroniza TODO Global automaticamente.
6. Preservar a rota e a autenticação existentes, sem criar site paralelo, autenticação falsa ou backend fictício.
7. A lista é um **inventário inicial não exaustivo**, com data da fonte, issue de referência e sinalização explícita de falta de prova. O Site “Divulgação de Evoluções” permanece fora do escopo por não ter vínculo comprovado com o ReqSys ou projeto relacionado.
8. Sites privados permanecem sem E2E e o acesso do proprietário não equivale a RBAC funcional comprovado.
9. Manter o ciclo cadastro → comparação → reaproveitamento → validação → integração aprovada → acompanhamento → consolidação com histórico, na issue #3149 e TODO Global.
10. Não incluir segredos nem informações privadas no frontend público. A permissão de leitura da rota é visual; controle efetivo de serviços externos requer auditoria separada.

## Critérios de aceite
1. IDs únicos e 18 registros iniciais reproduzidos a partir das fontes conferidas em 13/11/2026.
2. Oito URLs AppDeploy e três Sites privados relacionados conhecidos, todos marcados como publicadas **sem E2E**, nenhuma marcada operacional.
3. Links externos HTTPS seguros e nenhum token, senha, usuário ou parâmetro sensível.
4. Filtro positivo, negativo, case-insensitive e repetição idempotente, com estado vazio.
5. Componente renderiza os registros em `/painel-projetos` sem criar nova rota; manter política existente.
6. Testes de regressão em Vitest e build do frontend realmente executados no SHA.
7. Pre-PR Readiness Gate aprova o SHA exato, mantendo o gate SDD ativo.
8. Validação independente, autorização e E2E real são pendências **antes** de PR/merge/deploy conforme contratos globais; publicação não está autorizada.
9. Inventário e ciclo registrados no TODO Global por chave lógica estável; readback não prova integração automatizada.

## Evidências e limites
- Código: `frontend/src/data/catalogoAplicacoes.js`, `frontend/src/components/CatalogoAplicacoes.vue`, `frontend/src/views/PainelProjetosView.vue`.
- Testes: `frontend/src/components/__tests__/CatalogoAplicacoes.test.js`.
- GitHub: issue #3149; AppDeploy: enumeração de 10 apps, oito no escopo, sem teste E2E externo.
- A lista deve evoluir por evidência; não ocultar aplicações não auditadas, não eliminar código duplicado sem autorização.
