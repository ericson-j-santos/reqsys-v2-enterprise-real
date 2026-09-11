import pytest

from app.services.knewin_clipping import (
    build_clipping_record,
    build_idempotency_key,
    canonicalize_url,
    classify_relevance,
)


def test_canonicalize_url_removes_tracking_and_fragment():
    url = "https://Example.com/noticia/?utm_source=x&b=2&a=1#trecho"
    assert canonicalize_url(url) == "https://example.com/noticia?a=1&b=2"


def test_idempotency_key_is_stable_for_tracking_variants():
    first = build_idempotency_key(
        url="https://site.test/a?utm_source=x&id=10",
        publication_date="2026-08-31",
        vehicle="Mercado Comum",
    )
    second = build_idempotency_key(
        url="https://site.test/a?id=10&utm_campaign=y",
        publication_date="2026-08-31",
        vehicle="mercado comum",
    )
    assert first == second


def test_relevance_includes_explicit_fecap_spokesperson():
    status, reason = classify_relevance(
        title="Professor da FECAP explica déficit das contas públicas",
        snippet="Ahmed El Khatib comenta o cenário fiscal.",
    )
    assert status == "include"
    assert "participação editorial" in reason


def test_relevance_excludes_incidental_biography():
    status, reason = classify_relevance(
        title="Executivo formado pela FECAP assume nova posição",
        snippet="",
    )
    assert status == "exclude"
    assert "incidental" in reason


def test_relevance_sends_ambiguous_reference_to_review():
    status, _ = classify_relevance(
        title="Evento reúne FECAP e outras instituições",
        snippet="Agenda acadêmica de agosto.",
    )
    assert status == "review"


def test_build_record_maps_tier_and_business_unit():
    record = build_clipping_record(
        {
            "date": "2026-08-31",
            "vehicle": "Mercado Comum",
            "media": "Online",
            "origin": "Proativo",
            "subject": "Déficit das contas públicas",
            "source_person": "Ahmed El Khatib",
            "title": "Professor da FECAP explica déficit das contas públicas",
            "snippet": "Professor da FECAP comenta os números.",
            "url": "https://mercadocomum.test/materia?utm_source=knewin",
        },
        tier_by_vehicle={"Mercado Comum": "2"},
        business_unit_by_person={"Ahmed El Khatib": "Graduação"},
    )

    assert record.tier == "2"
    assert record.business_unit == "Graduação"
    assert record.relevance_status == "include"
    assert record.requires_review is False


def test_unknown_tier_requires_review_instead_of_inventing_value():
    record = build_clipping_record(
        {
            "date": "2026-08-31",
            "vehicle": "Veículo novo",
            "media": "Online",
            "origin": "Menção",
            "subject": "Tema",
            "title": "Professor da FECAP comenta tema",
            "url": "https://example.test/noticia",
        },
    )
    assert record.tier is None
    assert record.requires_review is True


def test_missing_required_field_fails_closed():
    with pytest.raises(ValueError, match="missing required fields: url"):
        build_clipping_record(
            {
                "date": "2026-08-31",
                "vehicle": "Mercado Comum",
                "media": "Online",
                "title": "Professor da FECAP comenta tema",
            }
        )


def test_invalid_url_fails_closed():
    with pytest.raises(ValueError, match="absolute http"):
        canonicalize_url("/noticia/123")
