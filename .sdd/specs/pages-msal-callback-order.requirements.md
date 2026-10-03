# Retorno Microsoft no GitHub Pages

## Objetivo

Garantir que o ReqSys consuma os parâmetros OAuth retornados pelo Microsoft Entra antes que o guard do roteador navegue para a tela de login.

## Critérios de aceite

- O retorno contendo `code` ou `error` é processado antes de montar o roteador.
- Visitas comuns continuam montando a interface antes da renovação silenciosa.
- Após a troca do token, o destino não preserva `code`, `state` ou o prefixo físico do Pages.
- Falhas do retorno continuam visíveis na tela de login.
