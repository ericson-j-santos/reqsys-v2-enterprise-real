# Fluxo — PR Quality Review

## Etapas

1. PR aberto ou sincronizado.
2. Workflow `PR Quality Review` executa.
3. Script coleta metadados e arquivos alterados.
4. Risco é classificado em `ok`, `warning` ou `critical`.
5. Relatórios JSON e Markdown são publicados como artifact.
6. Apenas `critical` falha o workflow.

## Fonte de verdade

O merge continua dependente dos checks obrigatórios, revisão humana quando aplicável e branch protection.
