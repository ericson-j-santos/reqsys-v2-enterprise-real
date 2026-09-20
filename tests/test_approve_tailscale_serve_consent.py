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


def test_oauth_mode_does_not_request_new_consent(monkeypatch):
    called = {"request": False}
    monkeypatch.setattr(m, "request_consent_url", lambda *_args, **_kwargs: called.__setitem__("request", True))
    monkeypatch.setattr(m.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        m,
        "browser_snapshot",
        lambda: {"windows": [{"buttons": ["Authorize tailscale"], "texts": ["Authorize application"]}]},
    )
    monkeypatch.setattr(
        m,
        "control_diagnostics",
        lambda _labels: [{"label": "Authorize tailscale", "enabled": True}],
    )
    monkeypatch.setattr(m, "click_exact", lambda label: (label == "Authorize tailscale", [{"method": "invoke"}]))
    result = m.run("authorize-github-oauth", 11443, 0)
    assert result["ok"] is True
    assert result["result"] == "github_oauth_authorized"
    assert called["request"] is False


def test_parser_accepts_diagnose_mode():
    args = m.parser().parse_args(["diagnose"])
    assert args.mode == "diagnose"


def test_oauth_grants_org_then_authorizes(monkeypatch):
    snapshots = [
        [
            {"label": "Grant", "enabled": True},
            {"label": "Authorize tailscale", "enabled": False},
        ],
        [
            {"label": "Grant", "enabled": False},
            {"label": "Authorize tailscale", "enabled": True},
        ],
    ]
    monkeypatch.setattr(m.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        m,
        "browser_snapshot",
        lambda: {"windows": [{"buttons": ["Grant", "Authorize tailscale"], "texts": []}]},
    )
    monkeypatch.setattr(
        m,
        "control_diagnostics",
        lambda _labels: snapshots.pop(0),
    )
    clicked = []
    monkeypatch.setattr(
        m,
        "click_exact",
        lambda label: (clicked.append(label) is None, [{"label": label, "method": "invoke"}]),
    )
    result = m.run("authorize-github-oauth", 11443, 0)
    assert result["ok"] is True
    assert result["result"] == "github_oauth_authorized"
    assert clicked == ["Grant", "Authorize tailscale"]


def test_parser_accepts_github_mobile_mode():
    args = m.parser().parse_args(["confirm-github-mobile"])
    assert args.mode == "confirm-github-mobile"


def test_github_mobile_mode_does_not_request_new_consent(monkeypatch):
    called = {"request": False}
    monkeypatch.setattr(m, "request_consent_url", lambda *_args, **_kwargs: called.__setitem__("request", True))
    monkeypatch.setattr(m.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        m,
        "browser_snapshot",
        lambda: {"windows": [{"buttons": ["Use GitHub Mobile"], "texts": ["Confirm access"]}]},
    )
    monkeypatch.setattr(m, "click_exact", lambda label: (label == "Use GitHub Mobile", [{"method": "invoke"}]))
    result = m.run("confirm-github-mobile", 11443, 0)
    assert result["ok"] is True
    assert result["result"] == "github_mobile_challenge_started"
    assert called["request"] is False
