from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "resolve_lifecycle_requirement_codes.py"
spec = importlib.util.spec_from_file_location("resolve_lifecycle_requirement_codes", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_resolve_requirement_codes_usa_titulo_corpo_e_branch_sem_duplicar():
    pulls = [
        {
            "number": 10,
            "html_url": "https://github.com/org/repo/pull/10",
            "title": "[REQ-123456789] entrega",
            "body": "Closes REQ-123456789 e atende req-987654321",
            "head": {"ref": "feat/REQ-111222333-entrega"},
        },
        {
            "number": 11,
            "html_url": "https://github.com/org/repo/pull/11",
            "title": "sem requisito",
            "body": None,
            "head": {"ref": "chore/cleanup"},
        },
    ]

    codes, sources = module.resolve_requirement_codes(pulls)

    assert codes == ["REQ-111222333", "REQ-123456789", "REQ-987654321"]
    assert sources == [
        {
            "pr_number": 10,
            "pr_url": "https://github.com/org/repo/pull/10",
            "codes": ["REQ-111222333", "REQ-123456789", "REQ-987654321"],
        }
    ]


def test_resolve_requirement_codes_nao_inventa_codigo_invalido():
    pulls = [
        {
            "number": 12,
            "title": "REQ-123 não é código canônico",
            "body": "REQ-12345678 e REQ-1234567890 também não são",
            "head": {"ref": "feat/REQ-ABCDEFGHI"},
        }
    ]

    codes, sources = module.resolve_requirement_codes(pulls)

    assert codes == []
    assert sources == []
