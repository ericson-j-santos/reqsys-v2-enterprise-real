from __future__ import annotations

import pytest

from scripts import replicate_requisitos_anonimizado as replicator
from scripts.runtime_url_policy import RuntimeURLPolicyError


def test_replicar_validates_all_runtime_urls_before_network(monkeypatch) -> None:
    reads: list[str] = []
    monkeypatch.setattr(replicator, "_get_json", lambda url: reads.append(url) or {"data": []})

    with pytest.raises(RuntimeURLPolicyError, match="Fly.io"):
        replicator.replicar(
            "https://api.prod.example",
            "https://reqsys-api-stg.fly.dev",
            execute=False,
            limit=None,
        )

    assert reads == []


def test_replicar_uses_explicit_authorized_runtimes(monkeypatch) -> None:
    reads: list[str] = []

    def fake_get(url: str) -> dict:
        reads.append(url)
        return {"data": []}

    monkeypatch.setattr(replicator, "_get_json", fake_get)

    result = replicator.replicar(
        "https://api.prod.example/",
        "https://api.stg.example/",
        execute=False,
        limit=None,
    )

    assert reads == [
        "https://api.prod.example/v1/requisitos",
        "https://api.stg.example/v1/requisitos",
    ]
    assert result["source"] == "https://api.prod.example"
    assert result["target"] == "https://api.stg.example"
