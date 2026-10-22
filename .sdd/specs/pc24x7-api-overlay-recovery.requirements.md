# Recuperação do overlay público da API PC24x7 DEV

## Contexto

Uma recriação isolada da API pode preservar projeto, porta e raiz do Compose, mas
perder o overlay público canônico enquanto frontend e nginx permanecem corretos.
O reconciliador deve recuperar somente esse drift conhecido e continuar bloqueando
qualquer identidade ambígua.

## Critérios de aceite

1. A recuperação só pode ocorrer em `DESKTOP-PDQK954`, no projeto DEV
   `wt-pc24x7-piloto` e na porta pública esperada.
2. Frontend e nginx devem existir com cardinalidade exata de um container por
   serviço, compartilhar a mesma raiz Compose da API e declarar o mesmo override
   administrativo.
3. Ambos os serviços irmãos devem declarar exatamente um
   `docker-compose.pc24x7-public-dev.yml` canônico e aplicá-lo por último.
4. Se qualquer prova estiver ausente, divergente ou ambígua, nenhuma mutação pode
   ocorrer e o erro deve permanecer `public_dev_runtime_identity_not_proven`.
5. Depois da prova de identidade, permanecem obrigatórios o fast-forward para um
   SHA pertencente a `origin/main`, a recriação verificada e o readback do mesmo
   SHA com autenticação pública sem login demo.
6. Staging e produção não podem ser tocados.
7. A comparação do overlay de trabalho com o blob versionado, tanto no
   reconciliador quanto no recriador interno, deve aplicar os mesmos
   `clean filters` do Git para o caminho canônico, sem falso bloqueio por
   conversão CRLF/LF no Windows.

## Evidência de teste

- `tests/test_reconcile_pc24x7_teams_dev_runtime.py` cobre o drift recuperável e o
  bloqueio quando um dos dois serviços irmãos não comprova o overlay canônico,
  além da normalização de CRLF pelos filtros do Git.
