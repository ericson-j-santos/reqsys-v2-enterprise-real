# PostgreSQL 16 nativo no backend-test

## Limite desta entrega

Candidato não executado, preparado sobre `3b4fa17a63c220685a4ecf42f81a75002555b835`.
Não há run, SHA de mudança, evidência real ou aceite ainda. O helper só pode ser
chamado em GitHub Actions Linux/Ubuntu 24.04 com contexto completo e usuário não
root. Testes offline usam mocks explicitamente e proíbem subprocessos reais.

## Por que a alteração

A migração elimina a dependência de pull/start de `services.postgres` no job
backend-test. Não corrige por si só falhas do produto, de cobertura, notifier,
fila do GitHub, admissão, quotas ou gateway. Não há mudanças nos outros jobs.
O runner ubuntu-24.04 oficial documenta PostgreSQL 16 pré-instalado. O helper
verifica os binários em runtime e falha fechado diante de drift; não instala
pacote e não inicia o serviço global do sistema.

## Fluxo preparado

1. Executar unittest offline do helper e do contrato.
2. Preservar instalação ODBC/Python e verificação anti-mojibake.
3. Criar PGDATA/socket aleatórios 0700 em RUNNER_TEMP e arquivos privados 0600.
4. Registrar somente a máscara da senha no canal de comandos do Actions;
   autenticar por pgpass. DATABASE_URL não contém a senha.
5. Iniciar apenas o cluster próprio e confirmar identidade, SELECT 1 e versão.
6. Rejeitar senha incorreta por autenticação, escrever marcador, ler por outra conexão, parar, exigir falhas reais de
   conexão/probe, reiniciar e reler o marcador persistido.
7. Remover tabela de prova e rodar a suíte backend inteira com cobertura 60.
8. Finalizar pelo trap; repetir cleanup idempotente em always.
9. Publicar somente artifacts preexistentes e recibo sanitizado.

A senha não vai para GITHUB_ENV, outputs, argumentos, URL ou artifact.
`PGPASSFILE` aponta para arquivo privado temporário; ele e o cluster são
removidos no cleanup. Os testes unitários existentes que usam SQLite não são
convertidos e não devem ser apresentados como testes PostgreSQL.

## Evidência futura exigida

- Pre-PR, admission e CI no mesmo HEAD final e base atual.
- Etapas efetivamente executadas, sem tratar skipped como sucesso.
- Artifact `backend-native-postgres-receipt` com contexto do run, instance_id,
  tool_versions, server_version_num, SELECT 1, leitura independente, falha com
  banco parado, persistência após reinício e cleanup=passed.
- Artifacts existentes de pytest/cobertura e cobertura mínima preservados.
- Inspeção de ausência de senha nos artifacts, sem copiar arquivos privados.

A descoberta automática de testes do Pre-PR usa os arquivos alterados, nome do
helper, referências ao workflow e pre_pr_tests no SDD. O workflow Pre-PR não é
modificado. Seu verde antecipa qualidade estática, não comprova o PostgreSQL real.

## Riscos e rollback

- Ubuntu 24.04 é rótulo móvel: ausência/major diferente/binários inconsistentes
  bloqueiam. Não há fallback para SQLite, Docker ou instalação privilegiada.
- Existe janela mínima entre escolher porta livre e o bind. Colisão bloqueia a
  própria inicialização; nenhum processo preexistente é interrompido.
- SIGKILL, perda de VM ou cancelamento forçado podem impedir traps/always. A VM
  hospedada é descartável; nunca afirmar cleanup comprovado sem recibo.
- Timeout de job proposto: 35 minutos, sem redução da suíte. Não é limite para
  fila do GitHub nem garantia de conclusão de toda janela de manutenção.
- A primeira execução real pode revelar diferenças de locale, dependências ou
  testes que assumiam porta 5432/senha fixa. Corrigir a causa no mesmo escopo e
  revalidar, sem enfraquecer gates.
- Rollback futuro: reverter somente este incremento, via fluxo governado,
  restaurando o bloco backend-test anterior. Não fazer rollback de gate,
  router, admissão ou fixtures de produto.

## Fontes oficiais e canônicas

- [Imagem Ubuntu 24.04](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)
- [PostgreSQL 16 initdb](https://www.postgresql.org/docs/16/app-initdb.html)
- [PostgreSQL 16 pg_ctl](https://www.postgresql.org/docs/16/app-pg-ctl.html)
- [SCRAM](https://www.postgresql.org/docs/16/auth-password.html)
- [Arquivo pgpass e permissões](https://www.postgresql.org/docs/16/libpq-pgpass.html)
- [Prontidão Pre-PR do projeto](pre-pr-readiness.md)
- [Validação canônica pré-entrega](https://github.com/ericson-j-santos/chatgpt-operational-rules/blob/main/rules/pre-delivery-validation.md)
