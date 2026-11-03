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
    assert 'github.rest.git.getRef' in block
    assert 'github.rest.repos.compareCommits' in block
    assert 'PR atrasada ou divergente' in block
    assert 'current.head.sha !== triggerHeadSha' in block
    assert 'current.base.sha !== currentBaseSha' in block
    assert 'currentComparison.behind_by > 0' in block
    assert "labelNames.includes('merge-queue:eligible')" in block
    assert "AUTO_MERGE_APPROVAL_LABEL: governed-merge-approved" in text
    assert "labelNames.includes(approvalLabel)" in block
    assert "merge_method: 'squash'" in block
    assert 'sha: triggerHeadSha' in block
    assert 'Deploy/promoção: não executados por este workflow.' in block


def test_ci_driven_automerge_exige_autorizacao_humana_explicita_por_pr() -> None:
    text = _text()

    marker = 'auto-merge-after-governed-queue:'
    block = text.split(marker, maxsplit=1)[1].split('  governed-pr-check:', maxsplit=1)[0]
    assert 'merge-queue:eligible' in block
    assert 'AUTO_MERGE_APPROVAL_LABEL: governed-merge-approved' in text
    assert 'const approvalLabel = process.env.AUTO_MERGE_APPROVAL_LABEL' in block
    assert 'labelNames.includes(approvalLabel)' in block
    assert 'currentLabelNames.includes(approvalLabel)' in block
    assert 'autorização humana explícita' in block


def test_ci_driven_automerge_revalida_estado_e_sha_imediatamente_antes_do_merge() -> None:
    text = _text()

    marker = 'auto-merge-after-governed-queue:'
    block = text.split(marker, maxsplit=1)[1].split('  governed-pr-check:', maxsplit=1)[0]
    assert 'const currentLabels = await github.paginate' in block
    assert "currentLabelNames.includes('merge-queue:eligible')" in block
    assert 'currentLabelNames.includes(approvalLabel)' in block
    assert 'current.head.sha !== triggerHeadSha' in block
    assert 'Estado mudou antes do merge' in block
    assert "github.rest.pulls.merge({" in block
    assert block.index("currentLabelNames.includes('merge-queue:eligible')") < block.index("github.rest.pulls.merge({")
    assert block.index('currentLabelNames.includes(approvalLabel)') < block.index("github.rest.pulls.merge({")


def test_governed_merge_materializa_validacao_pos_merge_nos_dois_caminhos() -> None:
    text = _text()

    assert text.count("github.rest.repos.createDispatchEvent({") == 2
    assert text.count("event_type: 'governed_post_merge_validation'") == 2
    assert "merge_sha: result.data.sha" in text
    assert "head_sha: triggerHeadSha" in text
    assert "head_sha: headSha" in text

def test_recovered_draft_is_promoted_to_ready_before_any_merge() -> None:
    text = _text()
    block = text.split('auto-merge-after-governed-queue:', maxsplit=1)[1].split('  governed-pr-check:', maxsplit=1)[0]
    assert "labelNames.includes('ci:recuperado')" in block
    assert "markPullRequestReadyForReview" in block
    assert "pullRequestId: currentDraft.node_id" in block
    assert "Merge: não executado neste ciclo" in block
    assert block.index("markPullRequestReadyForReview") < block.index("github.rest.pulls.merge({")



def test_review_independente_obrigatorio_para_merge_ci_driven_e_draft() -> None:
    block = _text().split('  auto-merge-after-governed-queue:', 1)[1].split('  governed-pr-check:', 1)[0]
    assert "github.rest.pulls.listReviews" in block
    assert "item.commit_id === sha" in block
    assert "item.state === 'APPROVED'" in block
    assert "item.state === 'CHANGES_REQUESTED'" in block
    assert "item.user.login.toLowerCase() !== pull.user?.login?.toLowerCase()" in block
    assert "!await hasIndependentHeadApproval(pr, triggerHeadSha)" in block
    assert "!await hasIndependentHeadApproval(currentDraft, triggerHeadSha)" in block
    assert "!await hasIndependentHeadApproval(current, triggerHeadSha)" in block
    assert block.index("!await hasIndependentHeadApproval(current, triggerHeadSha)") < block.index("github.rest.pulls.merge({")


def test_review_independente_obrigatorio_em_dispatch_manual_antes_do_merge() -> None:
    block = _text().split('  governed-pr-check:', 1)[1]
    assert "if (!await hasIndependentHeadApproval(pr, headSha))" in block
    assert "REVIEW_INDEPENDENT_HEAD_APPROVAL_REQUIRED_OR_HEAD_CHANGED" in block
    assert "current.head.sha !== headSha" in block
    assert block.index("hasIndependentHeadApproval(current, headSha)") < block.index("github.rest.pulls.merge({")


def test_autonomous_delivery_cycle_recusa_autor_bot_e_aprovacao_antiga() -> None:
    block = Path('.github/workflows/autonomous-delivery-cycle.yml').read_text(encoding='utf-8')
    for token in (
        "github.rest.pulls.listReviews", "item.state === 'APPROVED'",
        "item.state === 'CHANGES_REQUESTED'", "item.commit_id === sha",
        "item.user?.type === 'User'", "item.user.login.toLowerCase() !== pull.user?.login?.toLowerCase()",
        "REVIEW_INDEPENDENT_HEAD_APPROVAL_REQUIRED",
        "current.head.sha !== pr.head.sha",
    ):
        assert token in block
    assert block.index("!await hasIndependentHeadApproval(current, pr.head.sha)") < block.index("github.rest.pulls.merge({")
