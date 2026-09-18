# Resolução governada de papel

## Objetivo

Separar autenticação de autorização. O Microsoft Entra ID ou certificado prova a identidade; o ReqSys resolve o papel por fonte governada e nunca eleva privilégio por heurística de prefixo de e-mail.

## Precedência

1. `REQSYS_ROLE_BINDINGS`: JSON com identidade exata -> papel ReqSys.
2. App Roles do Entra ID, mapeadas por `REQSYS_ENTRA_ROLE_MAP`.
3. `REQSYS_DEFAULT_ROLE`, limitado a papel não privilegiado. O default é `analista`; `admin` como default é rejeitado e rebaixado para `analista`.

Papéis aceitos: `admin`, `analista`, `auditor`, `gestor`.

## Configuração DEV

Não registre identidades reais em issue, PR, log ou artifact público. Configure `REQSYS_ROLE_BINDINGS` no ambiente/cofre. Exemplo sanitizado:

```json
{
  "administrador@example.invalid": "admin",
  "operador@example.invalid": "gestor"
}
```

A configuração deve ser injetada no runtime, não commitada com identidades reais.

## Entra ID

O mapa padrão reconhece App Roles:

- `ReqSys.Admin` -> `admin`
- `ReqSys.Analyst` -> `analista`
- `ReqSys.Auditor` -> `auditor`
- `ReqSys.Manager` -> `gestor`

O mapa pode ser substituído por `REQSYS_ENTRA_ROLE_MAP`, em JSON, sem alteração de código.

## Evidência segura

A resposta autenticada informa `role_source`, com um dos valores:

- `configured_identity`
- `entra_app_role`
- `default_fail_closed`

Nenhum valor de `REQSYS_ROLE_BINDINGS`, token ou claim sensível deve ser emitido em log. Logs podem registrar apenas identidade mascarada, papel e `role_source`.

## Critério de aceite

- identidade explicitamente configurada recebe o papel configurado;
- App Role Entra reconhecida resolve o papel correspondente;
- identidade sem mapeamento não recebe `admin`;
- JSON inválido ou papel desconhecido falha fechado;
- `REQSYS_DEFAULT_ROLE=admin` não concede privilégio;
- endpoints administrativos permanecem protegidos no backend, independentemente do estado do frontend.
