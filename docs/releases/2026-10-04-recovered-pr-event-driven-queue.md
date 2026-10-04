# Fila recuperada event-driven — 2026-10-04

A fila `ci:recuperado` passa a usar eventos GitHub para sincronização, promoção de draft, merge por SHA, validação pós-merge, checkpoint e avanço da próxima PR.

O polling do ChatGPT deixa de ser necessário como motor técnico. Falhas transitórias usam PR CI Watch; falhas técnicas determinísticas elegíveis reutilizam Ollama CI Triage + Codex Worker Pool na própria branch. Casos sensíveis/não elegíveis permanecem fail-closed.
