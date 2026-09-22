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


def test_ci_driven_automerge_dispara_quando_fila_governada_conclui() -> None:
    text = _text()

    assert 'workflow_run:' in text
    assert '      - Governed Merge Queue' in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'pull_request'" in text
    assert 'schedule:' not in text


def test_ci_driven_automerge_e_fail_closed_por_head_sha() -> None:
    text = _text()

    marker = 'auto-merge-after-governed-queue:'
    block = text.split(marker, maxsplit=1)[1]
    assert 'context.payload.workflow_run.head_sha' in block
    assert 'pr.head.sha !== triggerHeadSha' in block
    assert 'current.head.sha !== triggerHeadSha' in block
    assert "labelNames.includes('merge-queue:eligible')" in block
    assert "merge_method: 'squash'" in block
    assert 'sha: triggerHeadSha' in block
    assert 'Deploy/promoção: não executados por este workflow.' in block


def test_ci_driven_automerge_exige_autorizacao_explicita_por_pr() -> None:
    text = _text()

    marker = 'auto-merge-after-governed-queue:'
    block = text.split(marker, maxsplit=1)[1]
    assert "const approvalLabel = 'governed-merge-approved';" in block
    assert "labelNames.includes(approvalLabel)" in block
    assert 'Merge governado aguardando autorizacao explicita' in block
    assert 'Autorizacao explicita ausente' not in block
    assert 'merge-queue:eligible' in block


def test_ci_driven_automerge_reage_a_label_de_aprovacao_sem_falso_ci_vermelho() -> None:
    text = _text()

    marker = 'auto-merge-after-governed-queue:'
    block = text.split(marker, maxsplit=1)[1]
    assert "github.event_name == 'pull_request'" in block
    assert "github.event.action == 'labeled'" in block
    assert "github.event.label.name == 'governed-merge-approved'" in block
    assert "context.eventName === 'workflow_run'" in block
    assert 'context.payload.pull_request.head.sha' in block


def test_ci_driven_automerge_revalida_autorizacao_imediatamente_antes_do_merge() -> None:
    text = _text()

    marker = 'auto-merge-after-governed-queue:'
    block = text.split(marker, maxsplit=1)[1]
    assert 'const currentLabels = await github.paginate' in block
    assert "currentLabelNames.includes('merge-queue:eligible')" in block
    assert 'currentLabelNames.includes(approvalLabel)' in block
    assert 'Estado ou autorizacao mudou antes do merge' in block
    assert "github.rest.pulls.merge({" in block
    assert block.index('currentLabelNames.includes(approvalLabel)') < block.index("github.rest.pulls.merge({")
