from pathlib import Path
import hashlib
import importlib.util
import json
import sys

MODULE_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'ocr_real_corpus_policy.py'
spec = importlib.util.spec_from_file_location('ocr_real_corpus_policy', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def _escrever_manifesto(tmp_path, corpus_root, *, pessoal=False, classificacao='ANONYMIZED_APPROVED'):
    arquivo = corpus_root / 'doc.png'
    arquivo.write_bytes(b'imagem-homologada-sem-pii')
    digest = hashlib.sha256(arquivo.read_bytes()).hexdigest()
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({
        'schema_version': '1.0.0',
        'approval_reference': 'CHANGE-1234',
        'contains_personal_data': pessoal,
        'cases': [{
            'case_id': 'REAL-001',
            'file': 'doc.png',
            'sha256': digest,
            'classification': classificacao,
            'contains_personal_data': pessoal,
            'expected': 'NOME HOMOLOGADO',
        }],
    }), encoding='utf-8')
    return manifest


def test_corpus_aprovado_fora_do_repo_e_integro_e_liberado(tmp_path):
    repo_root = tmp_path / 'repo'; repo_root.mkdir()
    corpus_root = tmp_path / 'secure-corpus'; corpus_root.mkdir()
    manifest = _escrever_manifesto(tmp_path, corpus_root)
    result = mod.validar_corpus(manifest, corpus_root, repo_root=repo_root)
    assert result['allowed'] is True
    assert result['content_exposed'] is False


def test_pii_declarada_bloqueia_corpus(tmp_path):
    repo_root = tmp_path / 'repo'; repo_root.mkdir()
    corpus_root = tmp_path / 'secure-corpus'; corpus_root.mkdir()
    manifest = _escrever_manifesto(tmp_path, corpus_root, pessoal=True)
    result = mod.validar_corpus(manifest, corpus_root, repo_root=repo_root)
    assert result['allowed'] is False
    assert 'MANIFEST_MUST_DECLARE_NO_PERSONAL_DATA' in result['failures']


def test_corpus_dentro_do_repositorio_e_classificacao_invalida_bloqueiam(tmp_path):
    repo_root = tmp_path / 'repo'; repo_root.mkdir()
    corpus_root = repo_root / 'real'; corpus_root.mkdir()
    manifest = _escrever_manifesto(tmp_path, corpus_root, classificacao='RAW_REAL')
    result = mod.validar_corpus(manifest, corpus_root, repo_root=repo_root)
    assert result['allowed'] is False
    assert 'CORPUS_ROOT_INSIDE_REPOSITORY' in result['failures']
    assert any('CLASSIFICATION_NOT_APPROVED' in item for item in result['failures'])


def test_hash_divergente_bloqueia(tmp_path):
    repo_root = tmp_path / 'repo'; repo_root.mkdir()
    corpus_root = tmp_path / 'secure-corpus'; corpus_root.mkdir()
    manifest = _escrever_manifesto(tmp_path, corpus_root)
    dados = json.loads(manifest.read_text(encoding='utf-8'))
    dados['cases'][0]['sha256'] = '0' * 64
    manifest.write_text(json.dumps(dados), encoding='utf-8')
    result = mod.validar_corpus(manifest, corpus_root, repo_root=repo_root)
    assert result['allowed'] is False
    assert any('SHA256_MISMATCH' in item for item in result['failures'])
