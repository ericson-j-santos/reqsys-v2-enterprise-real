# PostgreSQL 16 nativo e descartável no CI

## Estado

Candidato preparado em 23/10/2026 sobre `3b4fa17a63c220685a4ecf42f81a75002555b835`.
Não executado, não publicado e não homologado. Nenhum resultado de teste é presumido.

## Escopo e requisitos

1. Alterar apenas o job `backend-test` em `.github/workflows/ci.yml`; preservar admission, router, nomes dos checks e demais gates.
2. Usar `ubuntu-24.04` e somente os binários oficiais já presentes em `/usr/lib/postgresql/16/bin`, com major 16 e toolchain consistente. Ausência, outra major ou versão inconsistente bloqueia, sem instalação/fallback.
3. Criar PGDATA e socket próprios, privados e únicos em RUNNER_TEMP como usuário não root; nunca reutilizar ou parar um cluster preexistente.
4. Escutar somente em 127.0.0.1, em porta escolhida livre. Colisão entre a seleção e o bind deve falhar fechado, nunca interromper o dono da porta.
5. Usar SCRAM e senha local aleatória descartável, mascarada no log de Actions, em arquivos 0600 dentro de diretório 0700. Não exportar senha ou URL com senha nem publicar arquivos privados.
6. Exigir pg_isready, SELECT 1, identidade de PGDATA/endereço/porta/usuário/database e server_version_num da major 16.
7. Rejeitar senha incorreta com erro real de autenticação; fazer escrita/leitura independente, parada real, controle negativo que exija pg_isready=2 e psql=2, probe recusado, reinício e leitura persistida. Não usar mocks como evidência desse ensaio real.
8. Preservar Python 3.12, ODBC, requirements, anti-mojibake, backend/tests completo, pyproject.toml, cobertura mínima 60 e artifacts existentes.
9. Cleanup idempotente com verificação de ownership/PID/datadir, trap e always. Não executar kill global, systemctl, pg_ctlcluster, Docker ou comandos com privilégio para o PostgreSQL.
10. O único artifact adicional é recibo sanitizado ligado ao SHA/run/attempt/job/instance; nunca pgpass, PGDATA, socket, estado privado ou log bruto do PostgreSQL.
11. Pre-PR descobre os testes offline por nome/referência e declaração SDD, sem alterar o manifesto de admissão. O ensaio PostgreSQL real e a suíte backend ficam no CI admitido.
12. Fixtures SQLite unitárias já existentes permanecem intactas. Isso não é fallback do helper e não prova que toda a suíte usa PostgreSQL.

## Critérios de aceite pendentes

- unittest offline e contrato do workflow executados, incluindo controles de regressão;
- Pre-PR verde no HEAD final, base corrente e `behind_by=0`;
- ensaio real executado em ubuntu-24.04 no mesmo HEAD, sem etapas skipped;
- suíte backend completa e cobertura >=60 aprovadas;
- recibo com negativo real e cleanup aprovados, artifacts sem segredo;
- CI/gates obrigatórios completos no mesmo HEAD.

A preparação estática não autoriza publicação, execução, janela de manutenção,
merge, deploy, credencial persistente ou mudança de rede.
