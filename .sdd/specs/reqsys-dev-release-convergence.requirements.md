# Requisitos — convergência de release ReqSys DEV (Issue #3126)

## Situação comprovada
No run 41668437189, a API DEV publicou `97a8348e856292bece8b161217a92ffab2fb17da` enquanto a main era `f532573cafc13f7989d666e11acd87ab6fed3d0a`. O gate corretamente bloqueou a validação; a rotina de deploy disponível depende de Docker Compose e não é elegível sob a política atual sem Docker.

## Critérios de aceite
1. Diferenciar **main_sha**, **approved_release_sha** e **observed_sha**; nenhum avanço de main gera, sozinho, uma publicação aprovada.
2. Falhar fechado quando SHA, ambiente DEV, prova de aprovação, leitura independente, locator assinado ou frescor da evidência forem inválidos.
3. Uma release previamente aprovada e instalada pode permanecer convergente mesmo com main mais recente, exibindo `main_ahead_of_approved_release=true`.
4. Com release aprovada ainda não instalada, apresentar `DEPLOY_BLOCKED` com pré-condições ausentes ou `READY_FOR_GOVERNED_DEPLOY`; ambos **não** são sucesso operacional e não iniciam publicação.
5. A admissão de nova publicação exige rota **nativa**, runner compatível, backup, rollback e autorização específica; Docker é sempre recusado nesta camada.
6. A função é determinística e gera fingerprint SHA-256 estável para evitar retrigger sem mudança de evidência/estado.
7. Testes de caso positivo, negativo (produção, Docker, autorização ausente, SHA inválido, evidência antiga, sem readback), idempotência e regressão deverão passar.
8. O controlador é somente leitura; não possui token, rede, shell, instalação, merge ou execução de deploy.

## Limitações e integração posterior
- O campo `approval_readback_verified` deve ser preenchido somente por consumidor autorizado que realmente releu a aprovação oficial no GitHub; um JSON arbitrário não representa comprovação externa.
- Este incremento **não atualiza o DEV** nem substitui a validação atual em `validacao-acessos.yml`. A integração somente poderá ocorrer depois de possuir manifesto de release autorizado, runtime nativo com rollback e E2E no SHA exato.
- Gate de PR deve passar no HEAD exato. Requer Validator independente; caso contrário manter a alteração na branch e não abrir PR.
- Não desativar o runtime legado antes de backup/inventário/reversão/E2E da alternativa nativa.
