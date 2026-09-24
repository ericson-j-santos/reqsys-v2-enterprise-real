from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "vibe_security_gate.py"
SPEC = importlib.util.spec_from_file_location("vibe_security_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_risk_matrix_has_all_12_unique_risks():
    ids = [item.risk_id for item in gate.RISK_DEFINITIONS]
    assert ids == [f"{index:02d}" for index in range(1, 13)]
    assert len(set(ids)) == 12


def test_blocks_high_confidence_frontend_sql_xss_password_and_error_leak(tmp_path):
    write(tmp_path, "frontend/src/config.js", "const secret = import.meta.env.VITE_PRIVATE_API_KEY;\n")
    write(tmp_path, "frontend/src/view.js", "box.innerHTML = comment;\n")
    write(
        tmp_path,
        "backend/app/api.py",
        "\n".join(
            [
                'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                "digest = hashlib.sha256(password.encode()).hexdigest()",
                'raise HTTPException(status_code=500, detail=str(exc))',
            ]
        ),
    )
    findings, scanned = gate.scan_repository(tmp_path)
    assert scanned == 3
    blockers = {item.risk_id for item in findings if item.enforcement == "block"}
    assert {"01", "03", "05", "08", "12"} <= blockers


def test_contextual_risks_are_review_required_not_false_safe(tmp_path):
    write(
        tmp_path,
        "backend/app/routes.py",
        "\n".join(
            [
                "payload = await request.json()",
                "record = Model(**payload)",
                "result = agent.invoke_tool(model_output)",
                '@app.get("/projects/{id}")',
                "return db.where(id=project_id)",
                "response = httpx.get(target_url)",
                '@app.post("/login")',
                "def login(): pass",
                '@app.get("/admin/reports")',
                "def admin_reports(): pass",
                '@app.post("/signup")',
                "def signup(): pass",
            ]
        ),
    )
    findings, _ = gate.scan_repository(tmp_path)
    reviews = {item.risk_id for item in findings if item.enforcement == "review"}
    assert {"02", "04", "06", "07", "09", "10", "11"} <= reviews


def test_sanitized_and_parameterized_examples_do_not_create_blockers(tmp_path):
    write(
        tmp_path,
        "frontend/src/view.js",
        "box.textContent = comment;\nconst clean = DOMPurify.sanitize(html);\n",
    )
    write(
        tmp_path,
        "backend/app/repository.py",
        'cursor.execute("SELECT id FROM projects WHERE owner_id = %s AND name = %s", (owner_id, name))\n',
    )
    findings, _ = gate.scan_repository(tmp_path)
    assert [item for item in findings if item.enforcement == "block"] == []


def test_frontend_test_fixtures_are_excluded_but_production_xss_remains_blocking(tmp_path):
    write(tmp_path, "frontend/src/__tests__/fixture.js", "box.innerHTML = comment;\n")
    write(tmp_path, "frontend/src/component.test.js", "box.innerHTML = comment;\n")
    write(tmp_path, "frontend/src/view.js", 'const tpl = \'<div v-html="raw"></div>\';\n')

    findings, scanned = gate.scan_repository(tmp_path)

    assert scanned == 1
    blockers = [item for item in findings if item.risk_id == "05" and item.enforcement == "block"]
    assert len(blockers) == 1
    assert blockers[0].path == "frontend/src/view.js"


def test_explicit_dompurify_sanitization_downgrades_raw_html_sink_to_review(tmp_path):
    write(
        tmp_path,
        "frontend/src/view.js",
        'const clean = DOMPurify.sanitize(raw);\nconst tpl = \'<div v-html="clean"></div>\';\n',
    )

    findings, _ = gate.scan_repository(tmp_path)
    xss = [item for item in findings if item.risk_id == "05"]

    assert len(xss) == 1
    assert xss[0].enforcement == "review"
    assert xss[0].severity == "high"


def test_specs_view_accepts_only_verified_trusted_markdown_sanitizer(tmp_path):
    write(
        tmp_path,
        "frontend/src/views/SpecsView.vue",
        "import { renderMarkdown } from '../utils/markdownRenderer'\n"
        '<div v-html="renderMarkdown(content)"></div>\n',
    )
    write(
        tmp_path,
        "frontend/src/utils/markdownRenderer.js",
        "const clean = DOMPurify.sanitize(html);\nexport function renderMarkdown() { return clean }\n",
    )

    findings, _ = gate.scan_repository(tmp_path)
    xss = [item for item in findings if item.risk_id == "05"]

    assert len(xss) == 1
    assert xss[0].path == "frontend/src/views/SpecsView.vue"
    assert xss[0].enforcement == "review"


def test_specs_view_blocks_when_trusted_markdown_helper_loses_sanitization(tmp_path):
    write(
        tmp_path,
        "frontend/src/views/SpecsView.vue",
        "import { renderMarkdown } from '../utils/markdownRenderer'\n"
        '<div v-html="renderMarkdown(content)"></div>\n',
    )
    write(
        tmp_path,
        "frontend/src/utils/markdownRenderer.js",
        "export function renderMarkdown(html) { return html }\n",
    )

    findings, _ = gate.scan_repository(tmp_path)
    blockers = [item for item in findings if item.risk_id == "05" and item.enforcement == "block"]

    assert len(blockers) == 1
    assert blockers[0].path == "frontend/src/views/SpecsView.vue"


def test_report_always_contains_12_risk_rows_and_no_signal_is_not_pass_claim(tmp_path):
    write(tmp_path, "backend/app/ok.py", "value = 1\n")
    findings, scanned = gate.scan_repository(tmp_path)
    payload = gate.write_reports(tmp_path, tmp_path / "out", "all", scanned, findings)
    assert payload["status"] == "passed"
    assert len(payload["risks"]) == 12
    assert all(row["status"] == "no_signal" for row in payload["risks"])
    report = json.loads((tmp_path / "out" / "vibe-security-report.json").read_text(encoding="utf-8"))
    assert "não comprova segurança" in report["assurance_note"]


def test_negative_self_test_detects_known_failure():
    assert gate.self_test_negative() is True


def test_changed_line_scope_blocks_only_new_static_debt(tmp_path):
    write(
        tmp_path,
        "backend/app/api.py",
        "raise HTTPException(status_code=500, detail=str(exc))\nvalue = 1\n",
    )
    findings, _ = gate.scan_repository(tmp_path, include_paths={"backend/app/api.py"})

    legacy_filtered = gate.filter_blockers_to_changed_lines(
        findings,
        {"backend/app/api.py": {2}},
    )
    assert [item for item in legacy_filtered if item.enforcement == "block"] == []

    new_debt = gate.filter_blockers_to_changed_lines(
        findings,
        {"backend/app/api.py": {1}},
    )
    assert any(item.risk_id == "12" and item.enforcement == "block" for item in new_debt)


def test_load_changed_line_map_normalizes_and_rejects_noise(tmp_path):
    path = tmp_path / "changed-lines.json"
    path.write_text(
        json.dumps({"./backend/app/api.py": [1, "2", 0, "x"], "docs/x.md": []}),
        encoding="utf-8",
    )
    assert gate.load_changed_line_map(path) == {
        "backend/app/api.py": {1, 2},
        "docs/x.md": set(),
    }


def test_security_baseline_passes_changed_line_map_to_vibe_gate() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "security-baseline-gate.yml"
    ).read_text(encoding="utf-8")
    assert "changed-lines.json" in workflow
    assert 'args+=("--changed-files" "$CHANGED_FILES" "--changed-lines" "$CHANGED_LINES")' in workflow
