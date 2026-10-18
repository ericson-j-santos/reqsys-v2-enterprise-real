# Redmine DEV — correção da baseline de segurança em 18/10/2026

Referência: issue #1686. Este registro substitui somente os mínimos de segurança
anteriores em `docs/architecture/redmine-sync-queue.md`; não altera a propriedade
de campos nem o desenho da fila/lifecycle.

## Causa confirmada e correção

O gate anterior aceitava Redmine 6.0.11, 6.1.4 e 7.0.1. O Security Advisories
oficial consultado em 18/10/2026 informa que #44467 e #44468, envolvendo divulgação
de dados privados pela API, foram corrigidos em 6.1.5 e 7.0.2. A política antiga
não cobria esses avisos. Além disso, o parser descartava qualquer sufixo, aceitando
uma versão `.devel` ou `-rc1` como se fosse um release estável.

A correção em `scripts/redmine_version_gate.py` exige 6.1.5 na série 6.1 e 7.0.2
na série 7.0. A série 6.0 é bloqueada por ausência de correção homologada desses
avisos, não por EOL. O parser admite release ou `.stable` com revisão numérica
opcional e falha fechado para os demais sufixos. As assinaturas públicas e o
formato da decisão permanecem preservados; a configuração existente trata
`minimum=None` sem tentar formatá-lo como versão.

## Prevenção e limites da evidência

O teste versionado cobre 47 casos: aceitação nos limites, versões antes aceitas
que agora são vulneráveis, série sem correção, EOL, séries futuras, entradas
inválidas, sufixos não homologados, repetição idempotente e formatação.

Antes da publicação, as funções dos testes foram executadas em um interpretador
Python isolado, em memória, sem comandos no PC24x7. Resultado: 47 casos aprovados.
Substituir temporariamente o avaliador pelo original causou 14 falhas; após
restaurar a implementação final, os 47 casos passaram novamente. O blob original
foi conferido pelo SHA Git `e6c2c8a875913a46523fa1824faeeae9869f13c7`.

Essa prova não equivale a uma execução pytest/CI no checkout do repositório nem
a um E2E ReqSys ↔ Redmine. O Pre-PR Readiness existente deve executar os testes
alterados no HEAD publicado; não abrir PR sem `READY_FOR_PR=passed` nesse SHA.

## Continuidade segura

- Não recuperar o serviço DEV usando 6.1.4 como baseline de segurança atual.
- Confirmar release e digest oficiais da 6.1.5 e compatibilidade do runtime DEV
  existente antes da atualização. Não tocar a instância histórica principal.
- O script do build isolado ainda fixa um SHA antigo do ReqSys. Corrigir essa
  dependência com SHA explícito e revalidado; um build antigo verde não homologa
  a main atual. A causa específica do exit 1 anterior permanece não comprovada.
- Confirmar referências de segredos, projeto/usuário/API e SHA do PC24x7 por canal
  governado, sem imprimir valores. Não repetir deploy sem mudança de pré-condição.
- Executar ida/volta com leitura independente, caso negativo, replay sem duplicar
  e quarentena no mesmo SHA/ambiente. Somente depois validar projeção Redmine do
  TODO Global e habilitar recorrência.

Rollback do código: reverter o incremento preserva a interface anterior, mas
reabre a lacuna de segurança; não autoriza reconectar versão vulnerável.

## Fontes

- https://www.redmine.org/projects/redmine/wiki/Security_Advisories
- https://www.redmine.org/news/
- https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1686
