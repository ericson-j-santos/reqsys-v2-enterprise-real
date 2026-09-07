from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "attest_gitlab_mirror_identity.py"
SPEC = importlib.util.spec_from_file_location("attest_gitlab_mirror_identity", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
# Registrar antes de executar: `dataclasses` resolve anotações via sys.modules.
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


GUEST = 10
DEVELOPER = 30
MAINTAINER = 40


def identity(**overrides):
    base = {"id": 4242, "username": "reqsys-github-mirror", "name": "reqsys-github-mirror", "state": "active"}
    base.update(overrides)
    return MODULE.Identity(**base)


def fake_fetch(routes: dict[str, object], *, missing_status: int = 403):
    def fetch(path: str) -> MODULE.ApiResult:
        if path in routes:
            return MODULE.ApiResult(ok=True, status=200, payload=routes[path])
        return MODULE.ApiResult(ok=False, status=missing_status, error=f"HTTP {missing_status}")

    return fetch


# --- correlação identidade x credencial -------------------------------------


def test_read_identity_resolves_the_vault_owner() -> None:
    fetch = fake_fetch({"/user": {"id": 4242, "username": "reqsys-github-mirror", "name": "Mirror", "state": "active"}})
    resolved, error = MODULE.read_identity(fetch)
    assert error is None
    assert resolved.id == 4242
    assert resolved.username == "reqsys-github-mirror"


def test_read_identity_reports_failure_without_raising() -> None:
    resolved, error = MODULE.read_identity(fake_fetch({}, missing_status=401))
    assert resolved is None
    assert error == "HTTP 401"


def test_read_candidates_lists_homonymous_identities() -> None:
    fetch = fake_fetch(
        {
            "/projects/grupo%2Fprojeto/members/all?query=reqsys-github-mirror&per_page=100": [
                {"id": 4242, "username": "reqsys-github-mirror", "name": "Mirror", "access_level": GUEST},
                {"id": 9999, "username": "reqsys-github-mirror-legacy", "name": "Mirror", "access_level": MAINTAINER},
                {"id": 1, "username": "outra-pessoa", "name": "Outra", "access_level": MAINTAINER},
            ]
        }
    )
    candidates = MODULE.read_candidates(fetch, "grupo%2Fprojeto", "reqsys-github-mirror")
    assert [c["id"] for c in candidates] == [4242, 9999]
    assert candidates[0]["access_level_name"] == "guest"
    assert candidates[1]["access_level_name"] == "maintainer"


def test_collect_never_calls_write_endpoints() -> None:
    called: list[str] = []

    def fetch(path: str) -> MODULE.ApiResult:
        called.append(path)
        return MODULE.ApiResult(ok=False, status=404, error="HTTP 404")

    MODULE.collect(fetch, project_path="grupo/projeto", identity_name="mirror", target_branch="main")
    assert called
    assert all("/user" in p or "/projects/" in p or "personal_access_tokens" in p for p in called)


# --- allowances da branch protegida -----------------------------------------


def test_allowance_matches_explicit_user_entry() -> None:
    assert MODULE.allowance_matches({"user_id": 4242}, user_id=4242, access_level=GUEST) is True


def test_allowance_matches_by_access_level() -> None:
    assert MODULE.allowance_matches({"access_level": MAINTAINER}, user_id=4242, access_level=MAINTAINER) is True


def test_allowance_rejects_lower_access_level() -> None:
    assert MODULE.allowance_matches({"access_level": MAINTAINER}, user_id=4242, access_level=DEVELOPER) is False


def test_allowance_rejects_no_one_entry() -> None:
    assert MODULE.allowance_matches({"access_level": 0}, user_id=4242, access_level=MAINTAINER) is False


def test_allowance_rejects_other_user_entry() -> None:
    assert MODULE.allowance_matches({"user_id": 9999}, user_id=4242, access_level=GUEST) is False


def test_group_allowance_is_reported_as_unevaluable() -> None:
    protecao = {
        "name": "main",
        "allow_force_push": False,
        "push_access_levels": [{"group_id": 55}, {"access_level": MAINTAINER}],
    }
    assert [e["group_id"] for e in MODULE.unevaluable_allowances(protecao)] == [55]
    result = MODULE.classify_verdict(
        identity=identity(),
        membership={"access_level": GUEST},
        protected_branch=protecao,
        candidates=None,
    )
    assert result.verdict == MODULE.VERDICT_INSUFFICIENT
    assert any("não é avaliável automaticamente" in f for f in result.findings)


def test_direct_user_allowance_has_nothing_unevaluable() -> None:
    protecao = {"name": "main", "allow_force_push": False, "push_access_levels": [{"user_id": 4242}]}
    assert MODULE.unevaluable_allowances(protecao) == []


# --- veredito ----------------------------------------------------------------


def test_verdict_unresolved_without_identity() -> None:
    result = MODULE.classify_verdict(
        identity=None, membership=None, protected_branch=None, candidates=None
    )
    assert result.verdict == MODULE.VERDICT_UNRESOLVED


def test_verdict_undetermined_when_protection_is_unreadable() -> None:
    result = MODULE.classify_verdict(
        identity=identity(),
        membership={"access_level": GUEST, "access_level_name": "guest"},
        protected_branch=None,
        candidates=None,
    )
    assert result.verdict == MODULE.VERDICT_UNDETERMINED


def test_verdict_insufficient_reproduces_the_current_block() -> None:
    result = MODULE.classify_verdict(
        identity=identity(),
        membership={"access_level": GUEST, "access_level_name": "guest"},
        protected_branch={
            "name": "main",
            "allow_force_push": False,
            "push_access_levels": [{"access_level": MAINTAINER}],
        },
        candidates=[
            {"id": 4242, "username": "reqsys-github-mirror", "access_level_name": "guest"},
            {"id": 9999, "username": "reqsys-github-mirror", "access_level_name": "maintainer"},
        ],
    )
    assert result.verdict == MODULE.VERDICT_INSUFFICIENT
    assert any("homônima" in f for f in result.findings)


def test_verdict_authorized_after_minimal_grant() -> None:
    result = MODULE.classify_verdict(
        identity=identity(),
        membership={"access_level": GUEST, "access_level_name": "guest"},
        protected_branch={
            "name": "main",
            "allow_force_push": False,
            "push_access_levels": [{"user_id": 4242}],
        },
        candidates=None,
    )
    assert result.verdict == MODULE.VERDICT_AUTHORIZED


def test_verdict_flags_force_push_regression() -> None:
    result = MODULE.classify_verdict(
        identity=identity(),
        membership={"access_level": MAINTAINER, "access_level_name": "maintainer"},
        protected_branch={
            "name": "main",
            "allow_force_push": True,
            "push_access_levels": [{"user_id": 4242}],
        },
        candidates=None,
    )
    assert result.verdict == MODULE.VERDICT_FORCE_PUSH_ENABLED


def test_verdict_flags_token_owner_mismatch() -> None:
    result = MODULE.classify_verdict(
        identity=identity(),
        membership={"access_level": MAINTAINER},
        protected_branch={"name": "main", "allow_force_push": False, "push_access_levels": [{"user_id": 4242}]},
        candidates=None,
        token_metadata={"user_id": 9999, "revoked": False},
    )
    assert any("Divergência" in f for f in result.findings)


def test_verdict_flags_revoked_token() -> None:
    result = MODULE.classify_verdict(
        identity=identity(),
        membership={"access_level": MAINTAINER},
        protected_branch={"name": "main", "allow_force_push": False, "push_access_levels": [{"user_id": 4242}]},
        candidates=None,
        token_metadata={"user_id": 4242, "revoked": True},
    )
    assert any("revogado" in f for f in result.findings)


# --- ação humana e evidência -------------------------------------------------


def test_human_action_names_the_resolved_identity() -> None:
    action = MODULE.render_human_action(
        identity=identity(), credential_id="gitlab-main-mirror", target_branch="main"
    )
    assert "4242" in action["statement"]
    assert "fast-forward" in action["statement"]
    assert "force-push proibido" in action["statement"]


def test_evidence_omits_human_action_when_authorized() -> None:
    evidence = MODULE.build_evidence(
        project_path="grupo/projeto",
        target_branch="main",
        identity_name="reqsys-github-mirror",
        credential_id="gitlab-main-mirror",
        secret_name="reqsys-gitlab-main-mirror-token",
        identity=identity(),
        identity_error=None,
        token_metadata=None,
        candidates=None,
        membership=None,
        protected_branch=None,
        attestation=MODULE.Attestation(verdict=MODULE.VERDICT_AUTHORIZED),
    )
    assert evidence["remaining_human_action"] is None
    assert evidence["credential"]["secret_value_disclosed"] is False
    assert evidence["read_only"] is True


def test_write_evidence_blocks_secret_leak(tmp_path: Path) -> None:
    evidence = {"detail": "token glpat-supersecreto vazou"}
    with pytest.raises(MODULE.SecretLeakError):
        MODULE.write_evidence(tmp_path / "e.json", evidence, "glpat-supersecreto")
    assert not (tmp_path / "e.json").exists()


def test_write_evidence_persists_when_clean(tmp_path: Path) -> None:
    destino = tmp_path / "audit" / "e.json"
    MODULE.write_evidence(destino, {"verdict": MODULE.VERDICT_AUTHORIZED}, "glpat-supersecreto")
    assert json.loads(destino.read_text(encoding="utf-8"))["verdict"] == MODULE.VERDICT_AUTHORIZED


def test_main_is_fail_closed_without_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITLAB_MIRROR_TOKEN", raising=False)
    destino = tmp_path / "attestation.json"
    code = MODULE.main(["--evidence", str(destino)])
    assert code == 1
    evidence = json.loads(destino.read_text(encoding="utf-8"))
    assert evidence["verdict"] == MODULE.VERDICT_UNRESOLVED
    assert evidence["remaining_human_action"]["blocked_by"] == "identidade não resolvida"
