from pathlib import Path
import importlib.util
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "approve_tailscale_serve_consent.py"
SPEC = importlib.util.spec_from_file_location("approve_tailscale_serve_consent", SCRIPT)
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def test_extract_consent_url():
    url = m.extract_consent_url(
        "Serve is not enabled. To enable, visit: https://login.tailscale.com/f/serve?node=abc123"
    )
    assert url == "https://login.tailscale.com/f/serve?node=abc123"


def test_extract_consent_url_fails_closed():
    with pytest.raises(m.ConsentError, match="serve_consent_url_not_found"):
        m.extract_consent_url("no consent link")


def test_approval_target_prefers_exact_allowlist():
    snapshot = {"windows": [{"buttons": ["Cancel", "Enable Tailscale Serve"], "texts": []}]}
    assert m.approval_target(snapshot) == ("Enable Tailscale Serve", False)


def test_approval_target_marks_auth_without_click_target():
    snapshot = {"windows": [{"buttons": ["Sign in with GitHub"], "texts": ["Sign in"]}]}
    assert m.approval_target(snapshot) == (None, True)


def test_parser_accepts_explicit_github_login_mode():
    args = m.parser().parse_args(["login-github"])
    assert args.mode == "login-github"


def test_parser_accepts_explicit_github_oauth_mode():
    args = m.parser().parse_args(["authorize-github-oauth"])
    assert args.mode == "authorize-github-oauth"
