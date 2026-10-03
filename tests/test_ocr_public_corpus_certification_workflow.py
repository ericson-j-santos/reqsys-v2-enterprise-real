from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ocr-public-corpus-certification.yml"


def test_certificacao_ocr_executa_automaticamente_apos_merge_na_main() -> None:
    content = WORKFLOW.read_text(encoding="utf-8")

    push_block = content.split("  push:\n", maxsplit=1)[1].split("  schedule:\n", maxsplit=1)[0]
    assert "branches: [main]" in push_block
    assert "scripts/ocr_public_corpus_certify.py" in push_block
    assert ".github/workflows/ocr-public-corpus-certification.yml" in push_block

    certification_job = content.split("  certify-public-corpus:\n", maxsplit=1)[1]
    assert "github.event_name == 'push'" in certification_job
    assert "github.event_name == 'schedule'" in certification_job
    assert "github.event_name == 'workflow_dispatch'" in certification_job
