#!/usr/bin/env python3
"""Benchmark versionado do OCR de nomes do ReqSys.

Comandos:
- ``evaluate``: mede um JSONL de resultados já produzidos;
- ``synthetic``: renderiza e processa o corpus versionado do repositório;
- ``fetch-ibge``: atualiza snapshot explícito da API pública de Nomes do IBGE.

O snapshot IBGE é somente vocabulário de geração/teste. Nunca participa da
decisão do OCR nem é usado para autocorreção de nome reconhecido.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
CORPUS_PATH = ROOT / 'benchmark' / 'ocr' / 'corpus-v1.jsonl'
IBGE_SNAPSHOT_PATH = ROOT / 'benchmark' / 'ocr' / 'ibge-nomes-snapshot-v1.json'
IBGE_RANKING_URL = 'https://servicodados.ibge.gov.br/api/v2/censos/nomes/ranking'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from ocr_evidencia.adaptadores.ocr_tesseract import ConfiguracaoOCRNome, TesseractMultipass
from ocr_evidencia.dominio.nome import consensuar_nome, normalizar_nome_comparacao

CORPUS_VERSION = 'br-nomes-sinteticos-v1'

@dataclass(frozen=True)
class Metricas:
    casos: int
    caracteres_esperados: int
    erros_caractere: int
    cer: float
    exact_match: float
    auto_total: int
    false_auto_total: int
    false_auto: float
    auto_coverage: float

def _distancia(a: str, b: str) -> int:
    if not a:
        return len(b)
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(anterior[j] + 1, atual[j-1] + 1, anterior[j-1] + (ca != cb)))
        anterior = atual
    return anterior[-1]

def calcular_metricas(registros: list[dict]) -> Metricas:
    if not registros:
        raise ValueError('benchmark sem casos')
    erros = caracteres = exatos = autos = falsos_auto = 0
    for item in registros:
        esperado = normalizar_nome_comparacao(str(item['expected']))
        predito = normalizar_nome_comparacao(str(item.get('predicted', '')))
        estado = str(item.get('state', '')).upper()
        erros += _distancia(esperado, predito)
        caracteres += len(esperado)
        igual = esperado == predito
        exatos += int(igual)
        if estado == 'AUTO':
            autos += 1
            falsos_auto += int(not igual)
    total = len(registros)
    return Metricas(total, caracteres, erros, erros / max(caracteres, 1), exatos / total, autos, falsos_auto, falsos_auto / max(autos, 1), autos / total)

def avaliar_gate(metricas: Metricas, *, exact_min: float, cer_max: float, false_auto_max: float) -> list[str]:
    falhas = []
    if metricas.exact_match < exact_min:
        falhas.append(f'exact_match {metricas.exact_match:.4f} < {exact_min:.4f}')
    if metricas.cer > cer_max:
        falhas.append(f'cer {metricas.cer:.4f} > {cer_max:.4f}')
    if metricas.false_auto > false_auto_max:
        falhas.append(f'false_auto {metricas.false_auto:.4f} > {false_auto_max:.4f}')
    return falhas

def _carregar_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    registros = [json.loads(linha) for linha in path.read_text(encoding='utf-8').splitlines() if linha.strip()]
    if not registros:
        raise ValueError(f'corpus vazio: {path}')
    return registros

def carregar_corpus_versionado(path: Path = CORPUS_PATH) -> list[dict]:
    registros = _carregar_jsonl(path)
    ids: set[str] = set()
    for item in registros:
        case_id = str(item.get('case_id', '')).strip()
        expected = str(item.get('expected', '')).strip()
        if not case_id or not expected:
            raise ValueError('cada caso do corpus exige case_id e expected')
        if case_id in ids:
            raise ValueError(f'case_id duplicado: {case_id}')
        ids.add(case_id)
        if item.get('corpus_version') != CORPUS_VERSION:
            raise ValueError(f"versão de corpus incompatível em {case_id}: {item.get('corpus_version')}")
    return registros

def _renderizar_nome(nome: str, destino: Path, *, degradacao: dict | None = None) -> None:
    convert = shutil.which('magick') or shutil.which('convert')
    if not convert:
        raise RuntimeError('ImageMagick não encontrado')
    degradacao = degradacao or {}
    cmd = [convert, '-size', '1800x180', 'xc:white', '-gravity', 'center', '-font', 'DejaVu-Sans', '-pointsize', str(int(degradacao.get('pointsize', 64))), '-fill', 'black', '-annotate', '+0+0', nome]
    blur = float(degradacao.get('blur', 0.0))
    if blur > 0:
        cmd.extend(['-blur', f'0x{blur}'])
    rotacao = float(degradacao.get('rotation', 0.0))
    if rotacao:
        cmd.extend(['-background', 'white', '-rotate', str(rotacao)])
    cmd.append(str(destino))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())

def executar_sintetico(workdir: Path, *, corpus_path: Path = CORPUS_PATH) -> list[dict]:
    workdir.mkdir(parents=True, exist_ok=True)
    registros = []
    for indice, caso in enumerate(carregar_corpus_versionado(corpus_path), 1):
        nome = str(caso['expected'])
        imagem = workdir / f"{caso['case_id']}.png"
        _renderizar_nome(nome, imagem, degradacao=caso.get('degradation'))
        motor = TesseractMultipass(ConfiguracaoOCRNome(idioma='por', timeout_segundos=30))
        leituras = motor.executar(imagem, diretorio_trabalho=workdir / f'ocr-{indice:03d}').leituras
        resultado = consensuar_nome(leituras)
        registros.append({
            'case_id': caso['case_id'],
            'corpus_version': caso['corpus_version'],
            'source': caso.get('source', 'synthetic'),
            'expected': nome,
            'predicted': resultado.valor,
            'state': resultado.estado.value,
            'confidence': round(resultado.confianca, 6),
        })
    return registros

def baixar_amostra_ibge(destino: Path, limite: int = 20) -> dict:
    req = urllib.request.Request(IBGE_RANKING_URL, headers={'User-Agent': 'ReqSys-OCR-Benchmark/1.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
    payload = json.loads(raw.decode('utf-8'))
    ranking: list[dict] = []
    for bloco in payload:
        for item in bloco.get('res', []):
            nome = str(item.get('nome', '')).strip().upper()
            if nome:
                ranking.append({'nome': nome, 'frequencia': int(item.get('frequencia', 0)), 'ranking': int(item.get('ranking', 0))})
            if len(ranking) >= limite:
                break
        if len(ranking) >= limite:
            break
    snapshot = {
        'schema_version': '1.0.0',
        'snapshot_version': 'ibge-nomes-ranking-v1',
        'source': IBGE_RANKING_URL,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'purpose': 'synthetic-generator-vocabulary-only',
        'ranking': ranking,
    }
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return snapshot

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('ocr-benchmark.json'))
    parser.add_argument('--exact-min', type=float, default=0.90)
    parser.add_argument('--cer-max', type=float, default=0.02)
    parser.add_argument('--false-auto-max', type=float, default=0.0)
    sub = parser.add_subparsers(dest='command', required=True)
    e = sub.add_parser('evaluate'); e.add_argument('input', type=Path)
    s = sub.add_parser('synthetic'); s.add_argument('--workdir', type=Path); s.add_argument('--corpus', type=Path, default=CORPUS_PATH)
    i = sub.add_parser('fetch-ibge'); i.add_argument('--destination', type=Path, default=IBGE_SNAPSHOT_PATH); i.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    if args.command == 'fetch-ibge':
        snapshot = baixar_amostra_ibge(args.destination, max(1, args.limit))
        print(json.dumps({'destination': str(args.destination), 'names': len(snapshot['ranking']), 'source_sha256': snapshot['source_sha256']}, sort_keys=True))
        return 0
    registros = _carregar_jsonl(args.input) if args.command == 'evaluate' else executar_sintetico(args.workdir or Path(tempfile.mkdtemp(prefix='reqsys_ocr_benchmark_')), corpus_path=args.corpus)
    metricas = calcular_metricas(registros)
    falhas = avaliar_gate(metricas, exact_min=args.exact_min, cer_max=args.cer_max, false_auto_max=args.false_auto_max)
    saida = {'schema_version': '1.0.0', 'corpus_version': CORPUS_VERSION, 'metrics': asdict(metricas), 'thresholds': {'exact_min': args.exact_min, 'cer_max': args.cer_max, 'false_auto_max': args.false_auto_max}, 'gate': 'FAIL' if falhas else 'PASS', 'failures': falhas, 'cases': registros}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(saida['metrics'], ensure_ascii=False, sort_keys=True))
    if falhas:
        for falha in falhas:
            print(f'GATE: {falha}', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
