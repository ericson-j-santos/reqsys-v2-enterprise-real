# Fila recuperada event-driven — 2026-10-04

A fila `ci:recuperado` passa a usar eventos GitHub para sincronização, promoção de draft, merge por SHA, validação pós-merge, checkpoint e avanço da próxima PR.

O polling do ChatGPT deixa de ser necessário como motor técnico. Falhas determinísticas de código permanecem fail-closed até existir executor governado de edição do mesmo PR.
