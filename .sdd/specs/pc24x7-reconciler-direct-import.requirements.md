# PC24x7 reconciler — import direto no runner Windows

## Objetivo
Corrigir o ImportError observado quando o workflow executa `python scripts/reconcile_pc24x7_public_dev_runtime.py`.

## Requisitos
1. Não depender de `scripts` estar importável como pacote.
2. Carregar `self_hosted_dev_maintenance.py` pelo caminho irmão de `__file__`.
3. Preservar o comportamento atual do módulo.
4. Testar por subprocess o mesmo modo de execução direta usado no workflow.

## Critérios de aceite
- `python scripts/reconcile_pc24x7_public_dev_runtime.py --help` termina com exit 0.
- O código não contém o fallback de import que falhou no runner Windows.
- CI passa no HEAD exato.
- Após merge, o reconcile físico avança além da importação e produz evidência no SHA atual.
