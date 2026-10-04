# Política de Merge — Aba Estatísticas v1

## Estado do PR

O PR deve permanecer em draft até concluir:

- CI unitário verde;
- build do frontend verde;
- validação de rota/menu;
- revisão de segurança;
- revisão de governança de dados externos.

## Condições para ready for review

- Nenhum teste quebrado.
- Nenhum indicador inválido.
- Nenhum dado externo marcado como real sem fonte auditável.
- Nenhum estado atual avançado sem evidência.
- Sem conflito com PRs abertos que também alteram layout/router.

## Condições para merge

- CI verde.
- Revisão aprovada.
- Sem divergência da main.
- Changelog/release note atualizados.
- Próximo incremento documentado.
