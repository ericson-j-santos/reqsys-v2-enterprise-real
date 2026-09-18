from pathlib import Path


WORKFLOW = Path('.github/workflows/governed-pr-automation.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_workflow_dispatch_injeta_inputs_explicitamente_no_github_script() -> None:
    text = _text()

    assert 'PR_NUMBER_INPUT: ${{ github.event.inputs.pr_number }}' in text
    assert 'EXECUTE_MERGE_INPUT: ${{ github.event.inputs.execute_merge }}' in text
    assert 'REQUIRED_LABEL_INPUT: ${{ github.event.inputs.required_label }}' in text
    assert 'Number(process.env.PR_NUMBER_INPUT)' in text
    assert "process.env.EXECUTE_MERGE_INPUT === 'true'" in text
    assert 'process.env.REQUIRED_LABEL_INPUT' in text


def test_nao_usa_core_get_input_para_inputs_do_workflow_dispatch() -> None:
    text = _text()

    assert "core.getInput('pr_number')" not in text
    assert "core.getInput('execute_merge')" not in text
    assert "core.getInput('required_label')" not in text


def test_pr_number_invalido_falha_antes_de_chamar_api() -> None:
    text = _text()

    assert 'if [[ ! "$PR_NUMBER" =~ ^[1-9][0-9]*$ ]]' in text
    assert 'Number.isInteger(prNumber) || prNumber <= 0' in text
    assert 'pr_number invalido' in text


def test_lista_de_workflows_obrigatorios_preserva_quebras_de_linha() -> None:
    text = _text()

    assert 'REQUIRED_WORKFLOWS: |\n' in text
    assert 'REQUIRED_WORKFLOWS: >-' not in text
    assert ".split('\\n')" in text


def test_merge_reutiliza_pr_number_validado_do_dispatch() -> None:
    text = _text()

    marker = '- name: Merge PR when explicitly authorized'
    merge_block = text.split(marker, maxsplit=1)[1]
    assert 'PR_NUMBER_INPUT: ${{ github.event.inputs.pr_number }}' in merge_block
    assert 'Number(process.env.PR_NUMBER_INPUT)' in merge_block
    assert "core.getInput('pr_number')" not in merge_block
