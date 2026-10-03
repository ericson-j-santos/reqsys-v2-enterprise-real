# Callback Microsoft direto e diagnóstico persistente

## Objetivo

Eliminar a navegação intermediária do callback Microsoft no GitHub Pages e manter qualquer falha legível até a próxima tentativa do usuário.

## Critérios de aceite

- A raiz estável `/dev/` é usada diretamente como redirect URI no Pages.
- O aplicativo Entra preserva os redirects existentes e inclui a raiz estável.
- Um retorno OAuth sem ID token produz o código `MSAL_CALLBACK_WITHOUT_ID_TOKEN`.
- A mensagem é persistida sem armazenar código OAuth, ID token ou access token.
- Um login bem-sucedido remove o diagnóstico anterior.
