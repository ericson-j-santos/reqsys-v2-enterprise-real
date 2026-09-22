#!/usr/bin/env python3
"""Gera um serviço Python autocontido de notificações Teams (commits e ambientes).

Extraído de scripts/notificar_teams.py do ReqSys — 100% autônomo: todo o
conteúdo do serviço gerado (código + testes + docs) está embutido neste
próprio arquivo gerador como string literal. Rodar este único arquivo em
qualquer máquina com Python 3.11+ reproduz o pacote inteiro, sem precisar
do restante do repositório ReqSys clonado. Em tempo de execução, o serviço
gerado só precisa de acesso de rede ao Teams Messaging Gateway (por padrão
https://reqsys-api.fly.dev, configurável via --base-url/env var).

Uso:
    python tools/geradores/gerar_servico_notificador_repositorio.py --force --run-tests --zip
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

NOTIFIER = r'''
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://reqsys-api.fly.dev"


@dataclass(frozen=True)
class NotificacaoResultado:
    entregue: bool
    canal_usado: str | None = None
    correlation_id: str | None = None
    erro: str | None = None
    motivo: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def enviar_mensagem(
    *,
    base_url: str,
    texto: str,
    titulo: str,
    modo: str = "auto",
    destino_tipo: str = "chat",
    destino_id: str | None = None,
    autor: str = "repo-notifier",
    permitir_fallback: bool = True,
    dry_run: bool = False,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """Envia uma mensagem via Teams Messaging Gateway do ReqSys (POST /v1/teams-gateway/messages).

    Nao depende de nenhum arquivo/servico local: qualquer maquina com acesso de
    rede ao base_url consegue notificar. O gateway decide o canal real (webhook,
    flow_bot, graph_delegado etc.) - este modulo apenas envia a intencao.
    """
    payload = {
        "destino_tipo": destino_tipo,
        "modo": modo,
        "destino_id": destino_id,
        "texto": texto,
        "autor": autor,
        "permitir_fallback": permitir_fallback,
        "dry_run": dry_run,
        "metadata": {"titulo": titulo, "assinatura": "ReqSys"},
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/v1/teams-gateway/messages",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "teams-repo-notifier-service/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        return {"entregue": False, "erro": f"http_{exc.code}", "detail": exc.read().decode("utf-8", errors="ignore")}
    except (URLError, TimeoutError) as exc:
        return {"entregue": False, "erro": "network_error", "detail": str(exc)}

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        return {"entregue": False, "erro": "json_invalid", "detail": str(exc)}

    data = parsed.get("data") if isinstance(parsed, dict) else None
    if not isinstance(data, dict):
        return {"entregue": False, "erro": "payload_invalido", "detail": parsed}
    return data


def montar_texto_commit(*, sha: str, autor: str, mensagem: str, url: str = "", total_commits: int = 1) -> str:
    linha_mensagem = (mensagem or "(sem mensagem)").splitlines()[0]
    linhas = [
        f"Novo commit ({sha[:8]})",
        f"Autor: {autor or 'desconhecido'}",
        f"Mensagem: {linha_mensagem}",
    ]
    if total_commits > 1:
        linhas.append(f"Total de commits neste push: {total_commits}")
    if url:
        linhas.append(f"Link: {url}")
    return "\n".join(linhas)


def montar_texto_ambiente(*, ambiente: str, resultado: str, sha: str = "", detalhes_url: str = "") -> str:
    linhas = [f"Ambiente: {ambiente}", f"Resultado: {resultado}"]
    if sha:
        linhas.append(f"SHA: {sha[:8]}")
    if detalhes_url:
        linhas.append(f"Detalhes: {detalhes_url}")
    return "\n".join(linhas)


def _args_comuns(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--destino-id", default=os.environ.get("TEAMS_GATEWAY_DESTINO_ID"))
    parser.add_argument("--base-url", default=os.environ.get("TEAMS_GATEWAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--modo", default="auto")
    parser.add_argument("--destino-tipo", default="chat")
    parser.add_argument("--autor", default="repo-notifier")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--output")
    parser.add_argument("--strict", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Notifica o Teams sobre commits e ambientes, via o Teams Gateway do ReqSys")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_commit = sub.add_parser("commit", help="Notifica um novo commit/push")
    p_commit.add_argument("--sha", required=True)
    p_commit.add_argument("--autor-commit", required=True)
    p_commit.add_argument("--mensagem", required=True)
    p_commit.add_argument("--url", default="")
    p_commit.add_argument("--total-commits", type=int, default=1)
    _args_comuns(p_commit)

    p_ambiente = sub.add_parser("ambiente", help="Notifica o status de um ambiente/deploy")
    p_ambiente.add_argument("--nome", required=True)
    p_ambiente.add_argument("--resultado", required=True)
    p_ambiente.add_argument("--sha", default="")
    p_ambiente.add_argument("--detalhes-url", default="")
    _args_comuns(p_ambiente)

    args = parser.parse_args(argv)

    if args.comando == "commit":
        texto = montar_texto_commit(
            sha=args.sha, autor=args.autor_commit, mensagem=args.mensagem,
            url=args.url, total_commits=args.total_commits,
        )
        titulo = "ReqSys - Novo commit"
    else:
        texto = montar_texto_ambiente(
            ambiente=args.nome, resultado=args.resultado,
            sha=args.sha, detalhes_url=args.detalhes_url,
        )
        titulo = f"ReqSys - Ambiente {args.nome}: {args.resultado}"

    resultado = enviar_mensagem(
        base_url=args.base_url,
        texto=texto,
        titulo=titulo,
        modo=args.modo,
        destino_tipo=args.destino_tipo,
        destino_id=args.destino_id,
        autor=args.autor,
        permitir_fallback=not args.no_fallback,
        dry_run=args.dry_run,
        timeout=args.timeout,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(resultado, fh, ensure_ascii=False, indent=2)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))

    entregue = bool(resultado.get("entregue")) or bool(resultado.get("dry_run"))
    if not entregue:
        print(f"AVISO: notificacao nao entregue: {resultado.get('erro') or resultado.get('motivo')}", file=sys.stderr)
    if args.strict and not entregue:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''.lstrip()

NOTIFIER_TEST = r'''
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from service import enviar_mensagem, main, montar_texto_ambiente, montar_texto_commit


class _FakeResponse:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class MontarTextoTest(unittest.TestCase):
    def test_commit_usa_apenas_primeira_linha_da_mensagem(self):
        texto = montar_texto_commit(sha="abcdef1234567", autor="Fulano", mensagem="fix: bug\n\ndetalhe", url="https://x/y")
        self.assertIn("abcdef12", texto)
        self.assertIn("Fulano", texto)
        self.assertIn("fix: bug", texto)
        self.assertNotIn("detalhe", texto)
        self.assertIn("https://x/y", texto)

    def test_commit_total_maior_que_um(self):
        texto = montar_texto_commit(sha="abc", autor="F", mensagem="m", total_commits=3)
        self.assertIn("Total de commits neste push: 3", texto)

    def test_commit_autor_ausente(self):
        texto = montar_texto_commit(sha="abc", autor="", mensagem="m")
        self.assertIn("desconhecido", texto)

    def test_ambiente_texto(self):
        texto = montar_texto_ambiente(ambiente="producao", resultado="success", sha="deadbeef", detalhes_url="https://x")
        self.assertIn("Ambiente: producao", texto)
        self.assertIn("Resultado: success", texto)
        self.assertIn("deadbee", texto)


class EnviarMensagemTest(unittest.TestCase):
    def test_sucesso(self):
        with patch(
            "service.urlopen",
            return_value=_FakeResponse({"success": True, "data": {"entregue": True, "canal_usado": "flow_bot"}}),
        ):
            resultado = enviar_mensagem(base_url="https://example.invalid", texto="oi", titulo="T", destino_id="a@b.com")
        self.assertTrue(resultado["entregue"])
        self.assertEqual(resultado["canal_usado"], "flow_bot")

    def test_erro_rede(self):
        with patch("service.urlopen", side_effect=URLError("falhou")):
            resultado = enviar_mensagem(base_url="https://example.invalid", texto="oi", titulo="T", destino_id="a@b.com")
        self.assertFalse(resultado["entregue"])
        self.assertEqual(resultado["erro"], "network_error")


class MainCliTest(unittest.TestCase):
    def test_comando_commit_dry_run(self):
        argv = ["commit", "--sha", "abc123", "--autor-commit", "F", "--mensagem", "m", "--destino-id", "a@b.com", "--dry-run"]
        with patch(
            "service.urlopen",
            return_value=_FakeResponse({"success": True, "data": {"entregue": False, "dry_run": True}}),
        ):
            codigo = main(argv)
        self.assertEqual(codigo, 0)

    def test_comando_ambiente_strict_falha(self):
        argv = ["ambiente", "--nome", "prod", "--resultado", "failure", "--destino-id", "a@b.com", "--strict"]
        with patch("service.urlopen", side_effect=URLError("falhou")):
            codigo = main(argv)
        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
'''.lstrip()

README = (
    "# Teams Repo Notifier Service\n\n"
    "Serviço autocontido (stdlib apenas, sem dependências externas) para notificar "
    "o Teams sobre commits e ambientes, via o Teams Messaging Gateway do ReqSys. "
    "Gerado por `tools/geradores/gerar_servico_notificador_repositorio.py` — 100% "
    "autônomo: não depende de nenhum outro arquivo do repositório ReqSys, apenas "
    "de acesso de rede ao gateway (`https://reqsys-api.fly.dev` por padrão).\n\n"
    "## Uso\n\n"
    "```bash\n"
    "export TEAMS_GATEWAY_DESTINO_ID=usuario@tenant.onmicrosoft.com\n\n"
    "python src/service.py commit \\\n"
    "  --sha \"$(git rev-parse HEAD)\" \\\n"
    "  --autor-commit \"$(git log -1 --format=%an)\" \\\n"
    "  --mensagem \"$(git log -1 --format=%s)\"\n\n"
    "python src/service.py ambiente --nome producao --resultado success\n"
    "```\n\n"
    "Pode ser usado como git hook (`.git/hooks/post-commit`) ou step de CI de "
    "qualquer repositório — não precisa do ReqSys clonado, só deste diretório.\n\n"
    "## Testes\n\n"
    "```bash\n"
    "PYTHONPATH=src python -m unittest discover -s tests\n"
    "```\n"
)

FILES = {
    "teams-repo-notifier-service/README.md": README,
    "teams-repo-notifier-service/pyproject.toml": "[project]\nname='teams-repo-notifier-service'\nversion='1.0.0'\nrequires-python='>=3.11'\n",
    "teams-repo-notifier-service/src/service.py": NOTIFIER,
    "teams-repo-notifier-service/tests/test_service.py": NOTIFIER_TEST,
    "VALIDATION.md": "# Validação\n\nGerador validado localmente: 8 testes do serviço de notificação (montagem de texto, envio HTTP mockado, CLI commit/ambiente).\n",
}


def gerar(output: Path, force: bool) -> list[Path]:
    criados = []
    for nome, conteudo in FILES.items():
        destino = output / nome
        if destino.exists() and not force:
            raise FileExistsError(f"Arquivo já existe: {destino}. Use --force.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8", newline="\n")
        criados.append(destino)
    return criados


def testar(output: Path) -> None:
    raiz = output / "teams-repo-notifier-service"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(raiz / "src")
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(raiz / "tests")],
        cwd=raiz, env=env, check=True,
    )


def compactar(output: Path, destino_zip: Path) -> Path:
    destino_zip.parent.mkdir(parents=True, exist_ok=True)
    raiz = output / "teams-repo-notifier-service"
    with zipfile.ZipFile(destino_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for caminho in sorted(raiz.rglob("*")):
            if caminho.is_file() and "__pycache__" not in caminho.parts:
                zf.write(caminho, caminho.relative_to(output))
        validacao = output / "VALIDATION.md"
        if validacao.exists():
            zf.write(validacao, validacao.relative_to(output))
    return destino_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera o serviço autocontido de notificações Teams (commits/ambientes).")
    parser.add_argument("--output", default="artifacts/standalone-services")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--zip", dest="zip_path", nargs="?",
        const="artifacts/standalone-services/teams-repo-notifier-service.zip",
        help="Gera um .zip do serviço; aceita caminho customizado.",
    )
    args = parser.parse_args()
    output = Path(args.output).resolve()

    if args.dry_run:
        print(f"PRECHECK OK: {len(FILES)} arquivos seriam gerados em {output}")
        return 0

    criados = gerar(output, args.force)
    print(f"Gerados {len(criados)} arquivos em {output}")

    if args.run_tests:
        testar(output)
        print("TESTES OK: teams-repo-notifier-service")

    if args.zip_path:
        destino_zip = Path(args.zip_path).resolve()
        compactar(output, destino_zip)
        print(f"ZIP gerado em {destino_zip}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
