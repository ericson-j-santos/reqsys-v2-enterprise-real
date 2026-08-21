#!/usr/bin/env python3
"""Benchmark versionado do OCR de nomes do ReqSys.

Executa ``evaluate`` para medir JSONL, ``synthetic`` para gerar imagens e
executar o engine real, e ``fetch-ibge`` para criar snapshot versionado de
vocabulário público usado somente na geração sintética.
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
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from ocr_evidencia.adaptadores.ocr_tesseract import ConfiguracaoOCRNome, TesseractMultipass
from ocr_evidencia.dominio.nome import consensuar_nome, normalizar_nome_comparacao

CORPUS_VERSION = 'br-nomes-sinteticos-v1'
NOMES_CI = ('MARIA SILVA','JOAO SANTOS','ANA SOUZA','CARLOS ALMEIDA','LUIZ OLIVEIRA','ILSON LIMA','ISIS LUZ','BRUNO BARBOSA')

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

def _renderizar_nome(nome: str, destino: Path) -> None:
    convert = shutil.which('magick') or shutil.which('convert')
    if not convert:
        raise RuntimeError('ImageMagick não encontrado')
    cmd = [convert, '-size', '1800x180', 'xc:white', '-gravity', 'center', '-font', 'DejaVu-Sans', '-pointsize', '64', '-fill', 'black', '-annotate', '+0+0', nome, str(destino)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip())

def executar_sintetico(workdir: Path) -> list[dict]:
    workdir.mkdir(parents=True, exist_ok=True)
    registros = []
    for indice, nome in enumerate(NOMES_CI, 1):
        imagem = workdir / f'nome-{indice:03d}.png'
        _renderizar_nome(nome, imagem)
        motor = TesseractMultipass(ConfiguracaoOCRNome(idioma='por', timeout_segundos=30))
        leituras = motor.executar(imagem, diretorio_trabalho=workdir / f'ocr-{indice:03d}').leituras
        resultado = consensuar_nome(leituras)
        registros.append({'case_id': f'CI-{indice:03d}', 'corpus_version': CORPUS_VERSION, 'expected': nome, 'predicted': resultado.valor, 'state': resultado.estado.value, 'confidence': round(resultado.confianca, 6)})
    return registros

def baixar_amostra_ibge(destino: Path, limite: int = 20) -> dict:
    url = 'https://servicodados.ibge.gov.br/api/v2/censos/nomes/ranking'
    req = urllib.request.Request(url, headers={'User-Agent': 'ReqSys-OCR-Benchmark/1.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
    payload = json.loads(raw.decode('utf-8'))
    nomes = []
    for bloco in payload:
        for item in bloco.get('res', []):
            nome = str(item.get('nome', '')).strip().upper()
            if nome and nome not in nomes:
                nomes.append(nome)
            if len(nomes) >= limite:
                break
        if len(nomes) >= limite:
            break
    snapshot = {'schema_version': '1.0.0', 'source': url, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'purpose': 'synthetic-generator-vocabulary-only', 'names': nomes}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return snapshot

def _carregar_jsonl(path: Path) -> list[dict]:
    return [json.loads(linha) for linha in path.read_text(encoding='utf-8').splitlines() if linha.strip()]

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    e = sub.add_parser('evaluate'); e.add_argument('input', type=Path)
    s = sub.add_parser('synthetic'); s.add_argument('--workdir', type=Path)
    i = sub.add_parser('fetch-ibge'); i.add_argument('--destination', type=Path, default=ROOT / 'benchmark' / 'ocr' / 'ibge-nomes-snapshot.json'); i.add_argument('--limit', type=int, default=20)
    parser.add_argument('--output', type=Path, default=Path('ocr-benchmark.json'))
    parser.add_argument('--exact-min', type=float, default=0.90)
    parser.add_argument('--cer-max', type=float, default=0.02)
    parser.add_argument('--false-auto-max', type=float, default=0.0)
    args = parser.parse_args()
    if args.command == 'fetch-ibge':
        snapshot = baixar_amostra_ibge(args.destination, max(1, args.limit))
        print(json.dumps({'destination': str(args.destination), 'names': len(snapshot['names']), 'source_sha256': snapshot['source_sha256']}, sort_keys=True))
        return 0
    registros = _carregar_jsonl(args.input) if args.command == 'evaluate' else executar_sintetico(args.workdir or Path(tempfile.mkdtemp(prefix='reqsys_ocr_benchmark_')))
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
