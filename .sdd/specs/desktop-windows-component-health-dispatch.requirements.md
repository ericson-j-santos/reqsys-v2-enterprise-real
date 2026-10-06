# Desktop Windows Component Health Dispatch

## Objetivo

Expor em DEV uma rota administrativa fixa do ReqSys que despacha exclusivamente a capability governada `windows-component-health` para o Desktop PC24x7 Runtime.

## Contrato

- Endpoint: `POST /api/internal/desktop-control-plane/windows-component-health`.
- Requer a autenticação administrativa já aplicada às rotas internas.
- Aceita somente `correlation_id`; não aceita comando, caminho, host, executável ou argumentos.
- Publica somente o comentário exato `/desktop-runtime admin windows-component-health` na issue operacional governada.
- Reutiliza somente comentário recente, não editado, do owner e com corpo exatamente igual.
- O consumidor correspondente deve estar previamente disponível em `desktop-pc24x7-runtime`.
- `arbitrary_command_supported=false`, `remote_shell_used=false`, `production_touched=false`.

## Idempotência e evidência

A correlação HTTP é preservada na resposta. O broker deriva `desktop-admin-gh-comment-<id>`; no consumidor esse identificador chaveia o receipt e impede repetição dos diagnósticos concluídos.

## Segurança

Falha fechado fora de DEV, sem autenticação GitHub disponível, em divergência do correlation header ou quando o transporte GitHub não puder ser comprovado. Nenhum segredo é retornado.

## Critérios de aceite

1. comando diferente não é reutilizado;
2. repetição reutiliza somente comando exato e recente;
3. capability desconhecida/argumentada é rejeitada no consumidor;
4. E2E esperado: ReqSys → comentário GitHub → Desktop Admin Broker → DISM CheckHealth/ScanHealth + SFC verifyonly → receipt/readback.
