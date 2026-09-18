# Cofre PC24x7 — automação de credenciais e persistência

## Objetivo
Automatizar o ciclo de evidência do Cofre em DEV PC24x7 sem expor segredos e com persistência do keyring cifrado através de restart controlado.

## Requisitos
1. O JWT administrativo deve ser obtido por mecanismo DEV autorizado ou leitor do Cofre limitado a `human_admin_jwt:dev`.
2. O executor deve enviar JWT administrativo como `Authorization: Bearer`; `X-Service-Token` fica reservado a tokens de serviço.
3. O leitor escopado deve permitir recuperar o JWT sem colocá-lo em linha de comando, stdout, stderr, Git ou evidência pública.
4. A chave Fernet deve ser gerada de forma efêmera no `before-restart`, reutilizada no `after-restart` e removida após sucesso.
5. O Compose deve passar `COFRE_KEYRING_PASSPHRASE` sem valor embutido e definir `REQSYS_DATA_DIR=/data`.
6. O diretório `/data` da API deve usar volume persistente dedicado.
7. O fluxo deve falhar fechado se a passphrase não estiver configurada.
8. Escopo exclusivo DEV; produção não pode ser alterada.

## Critérios de aceite
1. Testes específicos do Cofre passam no SHA exato.
2. Regressão existente de `cofre_runtime_evidence.py` permanece verde.
3. Caso negativo de chave Fernet ausente continua falhando fechado.
4. Teste confirma `Authorization: Bearer` e ausência de uso do JWT como `X-Service-Token`.
5. Teste confirma passagem da passphrase e volume persistente `reqsys-cofre-data:/data`.
6. Repetição dos testes não altera estado do repositório.
7. Pre-PR Readiness termina `passed`, `behind_by=0`, SDD válido e sem bloqueadores.
8. Nenhum JWT, token do Cofre, chave Fernet ou passphrase aparece em evidência pública.
