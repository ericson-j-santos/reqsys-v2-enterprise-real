# Runbook — Cofre Runtime Evidence Gate

## Objetivo

Homologar o Cofre do ReqSys em DEV e STG com evidência reproduzível, sanitizada e bloqueante antes de qualquer promoção para produção.

## Escopo validado

1. consulta e, quando necessário, inicialização do Cofre;
2. criação de token S2S temporário escopado a uma única chave efêmera;
3. gravação e leitura do segredo sintético;
4. negação de acesso fora do escopo do token;
5. presença dos eventos de auditoria pelo `correlation_id`;
6. restart controlado de todas as máquinas Fly do ambiente;
7. persistência da chave mestra, token e segredo após restart;
8. exclusão do segredo e revogação do token temporário;
9. publicação de artefatos JSON sem valores sensíveis.

Produção não é aceita como entrada do workflow. O resultado verde de DEV e STG deve ser usado como pré-condição por workflows de promoção.

## Workflow

Arquivo: `.github/workflows/cofre-runtime-evidence-gate.yml`.

Execução manual:

1. abrir **Actions → Cofre Runtime Evidence Gate**;
2. selecionar `dev` ou `stg`;
3. executar com o GitHub Environment correspondente.

## Segredos por GitHub Environment

| Segredo | Finalidade |
| --- | --- |
| `COFRE_ADMIN_JWT` | JWT administrativo temporário usado nas rotas de gestão do Cofre |
| `FLY_API_TOKEN` | reinício controlado das máquinas do aplicativo Fly |

O JWT deve ter validade curta e ser rotacionado. Nenhum dos dois valores é incluído nos artefatos.

## Evidências

O artefato `cofre-runtime-evidence-<ambiente>-<run_id>` contém:

- `before-restart.json`;
- `after-restart.json`;
- `summary.json`.

São permitidos apenas metadados, hashes SHA-256, identificadores técnicos, tempos, status e `correlation_id`. O arquivo transitório com segredo e token é criado com permissão `0600` no diretório temporário do runner, removido ao final e nunca enviado como artefato.

## Critério de aprovação

O gate somente fica verde quando:

- o Cofre está inicializado;
- o token escopado funciona e bloqueia chave não autorizada;
- o segredo lido antes e depois do restart é idêntico;
- os eventos mínimos de auditoria existem;
- o cleanup remove o segredo e revoga o token;
- as duas fases geram evidências com `ok=true`.

## Falhas comuns

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| `401/403` em rotas administrativas | JWT expirado ou sem perfil admin | renovar `COFRE_ADMIN_JWT` no Environment |
| Cofre perde inicialização após restart | keyring/Secret Service não persistente no runtime | provisionar armazenamento/serviço de chave persistente antes de promover |
| `503 VAULT_API_TOKEN não configurado` | configuração S2S global ausente | configurar secret no ambiente; novos consumidores devem usar tokens escopados |
| auditoria ausente | falha de persistência ou propagação do `correlation_id` | investigar API e banco antes de repetir o gate |
| readiness não retorna após restart | incidente de deploy/runtime | consultar logs Fly e não promover |
