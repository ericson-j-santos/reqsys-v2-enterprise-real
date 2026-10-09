# Teams Bot direto via Key Vault no PC24x7 DEV

## Objetivo

Ativar o runtime Teams Bot em DEV no PC24x7 reutilizando a credencial existente do Azure Key Vault localmente, sem relay público efêmero, sem ampliar permissões e preservando o provedor Ollama já disponível no Desktop.

## Critérios de aceite

1. A execução é limitada ao ambiente DEV e exige confirmação explícita.
2. O runtime alvo deve corresponder exatamente ao SHA informado.
3. O token S2S `reqsys-pc24x7-teams-service-token` deve ser lido do Key Vault por OIDC
   somente depois da validação same-SHA e nunca aparecer em log ou evidência.
4. O token S2S deve ser removido do ambiente do job imediatamente após o E2E, inclusive
   quando a prova terminar em falha.
5. O override deve configurar o Bot e preservar o endpoint Ollama local do PC24x7.
6. O E2E deve separar dois modos de autenticação: `scoped-service-token`, padrão para a
   prova conversacional, e `ephemeral-admin`, preservado para a prova administrativa de
   emissão e revogação.
7. No modo S2S, o E2E deve exigir readiness `ready=true`, replay idempotente e entrega via
   canal `bot`, sem chamar as rotas administrativas de emissão/revogação e sem declarar
   que um token efêmero foi criado ou revogado.
8. No modo administrativo, o sucesso continua exigindo emissão e revogação confirmadas do
   token efêmero.
9. Evidência final deve registrar `auth_mode`, `token_lifecycle_applicable`,
   `secret_value_exposed=false` e `production_touched=false`.
10. Token S2S ausente, inválido, expirado ou sem o escopo requerido deve falhar fechado antes
    da criação da conversa, sem expor o valor.
11. `COFRE_ADMIN_JWT` deve ser injetado somente quando o modo `ephemeral-admin` for escolhido.
12. TEST/HML/STG/PROD permanecem fora do escopo.
13. Em falha de entrega, a evidência deve priorizar o status HTTP sanitizado já persistido
    pela fila para classificar o provedor, sem copiar corpo ou mensagem remota.

## Rastreabilidade

- #1532 — ativação da Central de Conversas IA/Teams em DEV.
- #993 — pendências operacionais ReqSys.
