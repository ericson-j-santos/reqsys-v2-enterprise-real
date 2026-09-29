#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SOURCE_URLS = {
    "permissions_reference": "https://learn.microsoft.com/en-us/graph/permissions-reference",
    "channel_list": "https://learn.microsoft.com/en-us/graph/api/channel-list-messages?view=graph-rest-1.0",
    "channel_post": "https://learn.microsoft.com/en-us/graph/api/channel-post-messages?view=graph-rest-1.0",
    "rsc": "https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent",
    "auth_service": "https://learn.microsoft.com/en-us/graph/auth-v2-service",
}
USER_AGENT = "ReqSys-Microsoft-Graph-Official-Monitor/1.0"
TIMEOUT_SECONDS = 25


class MonitorContractError(RuntimeError):
    pass


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)


def html_to_text(raw: str) -> str:
    parser = _TextExtractor()
    parser.feed(raw)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def fetch_official_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise MonitorContractError(f"official_source_unavailable:{url}:{exc}") from exc
    if status != 200:
        raise MonitorContractError(f"official_source_http_{status}:{url}")
    text = html_to_text(raw)
    if len(text) < 500:
        raise MonitorContractError(f"official_source_too_small:{url}")
    return text


def _permission_block(text: str) -> str:
    end_positions = [
        pos
        for marker in ("HTTP request", "Request headers")
        if (pos := text.find(marker)) >= 0
    ]
    if not end_positions:
        raise MonitorContractError("permissions_block_end_not_found")
    end = min(end_positions)
    start = text.rfind("Permissions", 0, end)
    if start < 0 or start >= end:
        raise MonitorContractError("permissions_block_start_not_found")
    block = text[start:end]
    if len(block) < 100:
        raise MonitorContractError("permissions_block_too_small")
    return block


def _admin_consent_pair(text: str, marker: str) -> tuple[str, str]:
    offset = 0
    while True:
        pos = text.find(marker, offset)
        if pos < 0:
            break
        window = text[pos : pos + 2200]
        match = re.search(
            r"AdminConsentRequired\s+(Yes|No|-)\s+(Yes|No|-)",
            window,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).lower(), match.group(2).lower()
        offset = pos + len(marker)
    raise MonitorContractError(f"admin_consent_contract_not_parsed:{marker}")


def _near(text: str, marker: str, radius: int = 700) -> str:
    pos = text.lower().find(marker.lower())
    if pos < 0:
        return ""
    start = max(0, pos - radius)
    return text[start : pos + len(marker) + radius]


def _event(
    code: str,
    change: str,
    effect: str,
    risk: str,
    adaptation: str,
    sources: list[str],
) -> dict[str, object]:
    return {
        "code": code,
        "change": change,
        "effect_on_current_blocker": effect,
        "risk": risk,
        "smallest_safe_idempotent_adaptation": adaptation,
        "sources": sources,
    }


def classify_documents(documents: dict[str, str]) -> dict[str, object]:
    missing = sorted(set(SOURCE_URLS).difference(documents))
    if missing:
        raise MonitorContractError("missing_documents:" + ",".join(missing))

    events: list[dict[str, object]] = []
    parser_errors: list[str] = []

    list_permissions = _permission_block(documents["channel_list"])
    post_permissions = _permission_block(documents["channel_post"])
    rsc_text = documents["rsc"]
    permissions_reference = documents["permissions_reference"]
    auth_text = documents["auth_service"]

    list_read_group = "ChannelMessage.Read.Group" in list_permissions
    rsc_read_group = "ChannelMessage.Read.Group" in rsc_text
    rsc_send_group = "ChannelMessage.Send.Group" in rsc_text

    if list_read_group != rsc_read_group:
        parser_errors.append("official_sources_disagree_on_ChannelMessage.Read.Group")
    elif not list_read_group:
        events.append(
            _event(
                "RSC_READ_GROUP_CHANGED",
                "ChannelMessage.Read.Group deixou de aparecer como caminho RSC de leitura nas duas referências oficiais monitoradas.",
                "O reconciliador DEV atual depende dessa permissão para provar a leitura independente das mensagens do canal.",
                "alto: o E2E pode voltar a 403 ou exigir outro modelo de consentimento.",
                "Manter fail-closed e não ampliar automaticamente para ChannelMessage.Read.All; validar a nova permissão em app RSC isolado e só então alterar manifest/reconciliador.",
                [SOURCE_URLS["channel_list"], SOURCE_URLS["rsc"]],
            )
        )

    if not rsc_send_group:
        events.append(
            _event(
                "RSC_SEND_GROUP_CHANGED",
                "ChannelMessage.Send.Group deixou de aparecer na referência oficial de RSC.",
                "Qualquer rota app-only de envio restrita ao Team deixa de ter o contrato oficial atual como suporte.",
                "médio/alto: ampliar para permissão tenant-wide ou envio delegado aumentaria privilégio.",
                "Preservar o caminho de envio atual e testar uma alternativa oficialmente documentada em DEV antes de trocar permissões.",
                [SOURCE_URLS["rsc"]],
            )
        )

    expected_post_tokens = {
        "ChannelMessage.Send",
        "Group.ReadWrite.All",
        "Teamwork.Migrate.All",
    }
    post_tokens = set(
        re.findall(
            r"\b(?:ChannelMessage|Group|Teamwork)[A-Za-z0-9.]*\b",
            post_permissions,
        )
    )
    if "ChannelMessage.Send" not in post_tokens:
        parser_errors.append("delegated_ChannelMessage.Send_not_parsed")
    if "Teamwork.Migrate.All" not in post_tokens:
        parser_errors.append("application_Teamwork.Migrate.All_not_parsed")

    new_post_tokens = sorted(post_tokens.difference(expected_post_tokens))
    if "ChannelMessage.Send.Group" in post_permissions or new_post_tokens:
        candidates = sorted(
            set(new_post_tokens)
            | ({"ChannelMessage.Send.Group"} if "ChannelMessage.Send.Group" in post_permissions else set())
        )
        events.append(
            _event(
                "CHANNEL_POST_PERMISSION_SURFACE_CHANGED",
                "A superfície oficial de permissões de POST em canal passou a expor permissões além do baseline: "
                + ", ".join(candidates),
                "Pode existir um novo caminho para envio no Graph que altere ou reduza o bloqueio atual do Planner→Teams.",
                "médio: adotar permissão nova sem validar escopo/consentimento pode ampliar acesso ou quebrar compatibilidade.",
                "Criar prova DEV isolada usando somente a nova permissão documentada, validar POST e readback por Graph e replay sem duplicidade; não remover o caminho atual antes dessa prova.",
                [SOURCE_URLS["channel_post"], SOURCE_URLS["rsc"]],
            )
        )

    admin_pair = _admin_consent_pair(
        permissions_reference,
        "ChannelMessage.Read.All",
    )
    if admin_pair != ("yes", "yes"):
        events.append(
            _event(
                "CHANNELMESSAGE_READ_ALL_ADMIN_CONSENT_CHANGED",
                "O requisito oficial de consentimento administrativo de ChannelMessage.Read.All mudou de Yes/Yes para "
                + "/".join(admin_pair),
                "Isso altera diretamente a necessidade de consentimento administrativo na alternativa tenant-wide de leitura.",
                "médio: uma mudança de consentimento não reduz por si só o escopo tenant-wide da permissão.",
                "Revalidar o fluxo de consentimento no tenant DEV e manter preferência por ChannelMessage.Read.Group RSC se o requisito funcional continuar restrito a um Team.",
                [SOURCE_URLS["permissions_reference"]],
            )
        )

    auth_window = _near(auth_text, "client credentials", radius=1200)
    auth_window += " " + _near(auth_text, "client_credentials", radius=1200)
    if not auth_window.strip():
        parser_errors.append("client_credentials_auth_contract_not_parsed")
    if re.search(
        r"\b(deprecat(?:ed|ion)|retir(?:ed|ement)|no longer supported|not supported)\b",
        auth_window,
        flags=re.IGNORECASE,
    ):
        events.append(
            _event(
                "GRAPH_APP_ONLY_AUTH_CHANGED",
                "A documentação oficial de autenticação passou a sinalizar retirada, depreciação ou falta de suporte próxima ao fluxo client credentials.",
                "O E2E e o reconciliador usam autenticação app-only para chamadas Graph; a obtenção do token pode precisar mudar.",
                "alto: falha de autenticação impediria tanto a prova de leitura quanto reconciliações automáticas.",
                "Não trocar credenciais ou grants automaticamente; validar o método sucessor documentado em identidade DEV federada e confirmar token + chamada Graph antes de alterar o runtime.",
                [SOURCE_URLS["auth_service"]],
            )
        )

    if parser_errors:
        raise MonitorContractError(";".join(sorted(parser_errors)))

    semantic = {
        "channel_list_application_read_group": list_read_group,
        "rsc_read_group": rsc_read_group,
        "rsc_send_group": rsc_send_group,
        "channel_post_tokens": sorted(post_tokens),
        "channelmessage_read_all_admin_consent": list(admin_pair),
        "auth_client_credentials_detected": bool(auth_window.strip()),
    }
    source_fingerprints = {
        key: hashlib.sha256(value.encode("utf-8")).hexdigest()
        for key, value in documents.items()
    }
    event_signature = hashlib.sha256(
        json.dumps(events, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:20]

    return {
        "schema_version": "1.0.0",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "state": "material_change" if events else "no_material_change",
        "material_change_count": len(events),
        "signature": event_signature,
        "baseline": {
            "ChannelMessage.Read.Group": "application RSC para leitura do Team",
            "ChannelMessage.Send.Group": "application RSC suportado pela referência Teams",
            "ChannelMessage.Read.All_admin_consent": "Yes/Yes",
            "channel_POST_delegated": "ChannelMessage.Send",
            "channel_POST_application": "Teamwork.Migrate.All (migração)",
            "app_only_auth": "client credentials",
        },
        "semantic_observations": semantic,
        "events": events,
        "official_sources": SOURCE_URLS,
        "source_fingerprints": source_fingerprints,
    }


def report_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Microsoft Graph — Planner→Teams",
        "",
        f"- Estado: **{report['state']}**",
        f"- Verificado em: {report['checked_at']}",
        f"- Assinatura: {report['signature']}",
        "",
    ]
    events = report.get("events", [])
    if not events:
        lines.append("Nenhuma mudança oficial material detectada no contrato monitorado.")
    else:
        for item in events:
            lines.extend(
                [
                    f"## {item['code']}",
                    "",
                    f"- Mudança confirmada: {item['change']}",
                    f"- Efeito no bloqueio atual: {item['effect_on_current_blocker']}",
                    f"- Risco: {item['risk']}",
                    f"- Menor adaptação segura e idempotente: {item['smallest_safe_idempotent_adaptation']}",
                    "- Fontes oficiais:",
                ]
            )
            lines.extend(f"  - {source}" for source in item["sources"])
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(
    report: dict[str, object],
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(report_markdown(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("artifacts/graph-official-monitor/report.json"),
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=Path("artifacts/graph-official-monitor/report.md"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        documents = {
            key: fetch_official_text(url)
            for key, url in SOURCE_URLS.items()
        }
        report = classify_documents(documents)
        write_outputs(report, args.json, args.markdown)
        return 0
    except MonitorContractError as exc:
        report = {
            "schema_version": "1.0.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "state": "monitor_error",
            "material_change_count": 0,
            "signature": hashlib.sha256(str(exc).encode("utf-8")).hexdigest()[:20],
            "error": str(exc),
            "events": [],
            "official_sources": SOURCE_URLS,
        }
        write_outputs(report, args.json, args.markdown)
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
