# Evidência operacional — Login Microsoft/Azure AD

## Identificação

| Campo | Valor |
|---|---|
| Data/hora | `<YYYY-MM-DD HH:mm:ss TZ>` |
| Ambiente | `<produção/homologação/desenvolvimento>` |
| Frontend | `<url>` |
| API | `<url>` |
| PR/commit | `<pr/sha>` |
| Operador | `<nome>` |

## Configuração pública

Executar:

```bash
python scripts/validar_login_azure_operacional.py \
  --api-url <api-url> \
  --expected-redirect-uri <frontend-origin>
```

Colar resultado:

```json
{
  "success": true,
  "errors": [],
  "warnings": []
}
```

## Checklist Microsoft Entra ID

| Item | Status | Evidência |
|---|---:|---|
| App Registration localizado | ☐ | `<nome/app id>` |
| Plataforma SPA configurada | ☐ | `<sim/não>` |
| Redirect URI do ambiente registrado | ☐ | `<uri>` |
| Tenant ID aplicado no backend | ☐ | `azure_enabled=true` |
| Client ID aplicado no backend | ☐ | `azure_enabled=true` |

## Teste E2E manual obrigatório

| Passo | Resultado esperado | Status |
|---|---|---:|
| Abrir frontend em janela anônima | Tela de login carrega | ☐ |
| Verificar botão Microsoft | Botão visível | ☐ |
| Clicar em Entrar com conta Microsoft | Popup Microsoft abre | ☐ |
| Autenticar usuário permitido | Popup retorna para aplicação | ☐ |
| Backend `/v1/auth/azure` aceita `id_token` | Sessão criada | ☐ |
| App redireciona para rota inicial | Usuário autenticado | ☐ |
| Recarregar página | Sessão preservada ou fluxo esperado | ☐ |
| Logout | Sessão encerrada | ☐ |

## Evidência visual

Anexar imagens sem expor tokens, código de autorização, e-mail sensível não necessário ou dados pessoais.

## Resultado final

| Critério | Status |
|---|---:|
| Login Microsoft corrigido no ambiente | ☐ |
| Produção sem login demo | ☐ |
| CI/gates verdes | ☐ |
| Evidência anexada ao PR | ☐ |

## Observações

- Não registrar `id_token`, `access_token`, authorization code, client secret, senha, CPF ou connection string.
- Se ocorrer `AADSTS50011`, corrigir Redirect URI no Microsoft Entra ID.
- Se `/v1/auth/config` retornar `auth_status=misconfigured`, corrigir secrets/variáveis antes de retestar.
