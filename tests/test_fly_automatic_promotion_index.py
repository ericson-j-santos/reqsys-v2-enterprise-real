from pathlib import Path


def test_index_links_workflow_contracts_and_architecture() -> None:
    index = Path("docs/README_FLY_AUTOMATIC_PROMOTION.md").read_text(encoding="utf-8")
    assert ".github/workflows/fly-automatic-environment-promotion.yml" in index
    assert "fly-automatic-environment-promotion.schema.json" in index
    assert "fly-automatic-promotion-flow.md" in index
