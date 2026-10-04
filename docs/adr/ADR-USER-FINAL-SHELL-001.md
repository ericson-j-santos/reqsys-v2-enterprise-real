# ADR-USER-FINAL-SHELL-001 — Shell de Produto do Usuário Final

## Status

Proposto.

## Contexto

O ReqSys precisa de uma camada inicial navegável para usuário final, com ambiente visível, estados operacionais padronizados e preparação para drill-down.

## Decisão

Criar um shell transversal de produto com rotas protegidas para:

- `/home`
- `/workspace`
- `/analytics`
- `/ajuda`

O shell deve preservar governança, não promover produção e não alterar gates de segurança.

## Requisitos mínimos

- Navegação interna clara.
- Indicador de ambiente `DEV`, `HML` ou `PRD`.
- Estados `loading`, `empty`, `error`, `success` e `unauthorized`.
- Cards clicáveis com preparação para drill-down.
- Rodapé técnico com versão, ambiente e `correlation_id` local seguro.
- Layout responsivo.

## Produção

Produção permanece bloqueada se houver auth desligada, CORS aberto, JWT sem validação real, logs com segredo/PII ou auditoria sem `correlation_id`.

## Consequências

O incremento libera uma experiência inicial sem acoplar persistência, RBAC completo ou deploy. A exposição no menu lateral global fica para incremento pequeno posterior.
