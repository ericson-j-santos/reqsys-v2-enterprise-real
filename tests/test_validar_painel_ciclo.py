from __future__ import annotations

import pytest

from scripts import validar_painel_ciclo as validator


def valid_bootstrap():
    return {
        "schema_version": "2.0.0",
        "mode": "bootstrap",
        "message": "Estado ao vivo indisponível.",
    }


def valid_projects():
    return {
        "repositories": [
            {"repository": "ericson-j-santos/reqsys-v2-enterprise-real"},
            {"repository": "ericson-j-santos/desktop-pc24x7-runtime"},
            {"repository": "ericson-j-santos/painel-powerbi"},
            {"repository": "ericson-j-santos/chatgpt-operational-rules"},
        ]
    }


def valid_html():
    return """
    <!doctype html><html><body>
    GitHub Microsoft Teams Certificação SLO TODO Global Runtime PC24x7 Power BI
    <script>fetch('global-status.json')</script>
    </body></html>
    """


def test_live_dashboard_contract_accepts_dynamic_source():
    validator.validate_contract(valid_html(), valid_bootstrap(), valid_projects())


def test_live_dashboard_contract_rejects_embedded_operational_state():
    html = (
        valid_html()
        + '<script id="estado-ciclo" type="application/json">{"frentes":[]}</script>'
    )

    with pytest.raises(SystemExit):
        validator.validate_contract(html, valid_bootstrap(), valid_projects())


def test_live_dashboard_contract_rejects_static_operational_bootstrap():
    bootstrap = valid_bootstrap()
    bootstrap["frentes"] = [{"pr": 18, "status": "concluido"}]

    with pytest.raises(SystemExit):
        validator.validate_contract(valid_html(), bootstrap, valid_projects())


def test_live_dashboard_contract_requires_core_projects():
    projects = valid_projects()
    projects["repositories"] = [
        item
        for item in projects["repositories"]
        if item["repository"] != "ericson-j-santos/painel-powerbi"
    ]

    with pytest.raises(SystemExit):
        validator.validate_contract(valid_html(), valid_bootstrap(), projects)
