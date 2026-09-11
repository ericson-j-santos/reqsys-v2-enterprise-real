from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}


@dataclass(frozen=True)
class ClippingRecord:
    date: str
    vehicle: str
    tier: str | None
    media: str
    origin: str | None
    subject: str | None
    source_person: str | None
    business_unit: str | None
    title: str
    url: str
    relevance_status: str
    relevance_reason: str
    idempotency_key: str
    requires_review: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonicalize_url(url: str) -> str:
    if not url or not url.strip():
        raise ValueError("url is required")
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("url must be absolute http(s)")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS]
    query.sort()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def build_idempotency_key(*, url: str, publication_date: str, vehicle: str) -> str:
    canonical = canonicalize_url(url)
    material = f"{canonical}|{publication_date.strip()}|{vehicle.strip().casefold()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def classify_relevance(*, title: str, snippet: str = "") -> tuple[str, str]:
    text = f"{title} {snippet}".casefold()
    if "fecap" not in text:
        return "exclude", "sem referência à FECAP"

    strong_signals = (
        "professor da fecap",
        "professora da fecap",
        "coordenador da fecap",
        "coordenadora da fecap",
        "especialista da fecap",
        "segundo a fecap",
        "fecap afirma",
        "fecap explica",
    )
    incidental_signals = (
        "formado pela fecap",
        "formada pela fecap",
        "estudou na fecap",
        "lista de instituições",
    )

    if any(signal in text for signal in strong_signals):
        return "include", "participação editorial explícita da FECAP ou de porta-voz"
    if any(signal in text for signal in incidental_signals):
        return "exclude", "referência incidental/biográfica"
    return "review", "referência à FECAP sem contexto suficiente para decisão automática"


def build_clipping_record(
    raw: Mapping[str, Any],
    *,
    tier_by_vehicle: Mapping[str, str] | None = None,
    business_unit_by_person: Mapping[str, str] | None = None,
) -> ClippingRecord:
    required = ("date", "vehicle", "media", "title", "url")
    missing = [name for name in required if not str(raw.get(name, "")).strip()]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    date = str(raw["date"]).strip()
    vehicle = str(raw["vehicle"]).strip()
    media = str(raw["media"]).strip()
    title = str(raw["title"]).strip()
    url = canonicalize_url(str(raw["url"]))
    snippet = str(raw.get("snippet", "")).strip()
    source_person = str(raw.get("source_person", "")).strip() or None

    tier_map = {k.casefold(): v for k, v in (tier_by_vehicle or {}).items()}
    unit_map = {k.casefold(): v for k, v in (business_unit_by_person or {}).items()}
    tier = tier_map.get(vehicle.casefold())
    business_unit = unit_map.get(source_person.casefold()) if source_person else None

    relevance_status, relevance_reason = classify_relevance(title=title, snippet=snippet)
    origin = str(raw.get("origin", "")).strip() or None
    subject = str(raw.get("subject", "")).strip() or None

    requires_review = (
        relevance_status == "review"
        or tier is None
        or origin is None
        or subject is None
        or (source_person is not None and business_unit is None)
    )

    return ClippingRecord(
        date=date,
        vehicle=vehicle,
        tier=tier,
        media=media,
        origin=origin,
        subject=subject,
        source_person=source_person,
        business_unit=business_unit,
        title=title,
        url=url,
        relevance_status=relevance_status,
        relevance_reason=relevance_reason,
        idempotency_key=build_idempotency_key(url=url, publication_date=date, vehicle=vehicle),
        requires_review=requires_review,
    )
