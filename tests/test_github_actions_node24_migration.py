from pathlib import Path


WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
LOCAL_ACTIONS = Path(__file__).resolve().parents[1] / ".github" / "actions"

NODE20_SHAS = {
    "0057852bfaa89a56745cba8c7296529d2fc39830",
    "11bd71901bbe5b1630ceea73d27597364c9af683",
    "11d5960a326750d5838078e36cf38b85af677262",
    "983d7736d9b0ae728b81ab479565c72886d7745b",
    "fee1f7d63c2ff003460e3d139729b119787bc349",
    "d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
    "d3f86a106a0bac45b974a628896c90dbdf5c8093",
    "60a0d83039c74a4aee543508d2ffcb1c3799cdea",
    "f28e40c7f34bde8b3046d885e986cb6290c5673b",
    "49933ea5288caeca8642d1e84afbd3f7d6820020",
    "a26af69be951a213d495a4c3e4e4022e16d87065",
    "ea165f8d65b6e75b540449e92b4886f43607fa02",
    "7184910d9eb2b1c5e48f7073824a90609bb9b6d6",
    "10e90e3645eae34f1e60eeb005ba3a3d33f178e8",
    "c94ce9fb468520275223c153574b00df6fe4bcc9",
    "8d2750c68a42422c14e847fe6c8ac0403b4cbd6f",
    "fcfb566f8b0aab22203f066d80ca1d7e4b5d05b3",
}

NODE20_MUTABLE_REFS = {
    "actions/cache@v4",
    "actions/checkout@v4",
    "actions/create-github-app-token@v2",
    "actions/download-artifact@v4",
    "actions/github-script@v7",
    "actions/setup-java@v4",
    "actions/setup-node@v4",
    "actions/setup-python@v4",
    "actions/setup-python@v5",
    "actions/stale@v9",
    "actions/upload-artifact@v4",
    "azure/login@v2",
    "dawidd6/action-download-artifact@v6",
    "dawidd6/action-download-artifact@v11",
    "gitleaks/gitleaks-action@v2",
}

NODE24_REFS = {
    "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9",
    "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d",
    "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1",
    "actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346",
    "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
    "actions/github-script@3a2844b7e9c422d3c10d287c895573f7108da1b3",
    "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",
    "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "azure/login@a641126d1b8aa4d1fa005f4f92df94a3a4c4c906",
    "docker/build-push-action@c3c9e263c25d99ce0380d002d59b67737d91b0dc",
    "docker/login-action@dbcb813823bdd20940b903addbd779551569679f",
    "docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069",
    "slackapi/slack-github-action@dcb1066f776dd043e64d0e8ba94ca15cc7e1875d",
    "actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6",
    "actions/stale@4391f3da665fdf50b6810c1a66712fb9ba21aa93",
    "dawidd6/action-download-artifact@eab87c9830c39eff17e5a6eadb20bfb4bc880477",
    "gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e",
}


def _workflow_source() -> str:
    workflow_files = sorted(WORKFLOWS.glob("*.y*ml"))
    action_files = sorted(LOCAL_ACTIONS.glob("*/action.y*ml"))
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in [*workflow_files, *action_files]
    )


def test_workflows_nao_referenciam_shas_node20_mapeados() -> None:
    source = _workflow_source()
    remaining = sorted(sha for sha in NODE20_SHAS if sha in source)
    assert remaining == []


def test_workflows_nao_referenciam_tags_mutaveis_node20() -> None:
    source = _workflow_source()
    remaining = sorted(ref for ref in NODE20_MUTABLE_REFS if ref in source)
    assert remaining == []


def test_releases_node24_aprovadas_estao_fixadas_por_sha() -> None:
    source = _workflow_source()
    missing = sorted(ref for ref in NODE24_REFS if ref not in source)
    assert missing == []
