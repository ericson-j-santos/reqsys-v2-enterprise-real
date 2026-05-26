import re
from datetime import date
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.envelope import ok, erro
from app.core.config import settings

router = APIRouter(prefix='/v1/specs', tags=['Specs SDD'])


# ---------------------------------------------------------------------------
# Helpers de path
# ---------------------------------------------------------------------------

def _sdd_root() -> Path:
    raw = settings.sdd_specs_path
    if not raw:
        raise HTTPException(503, 'SDD_SPECS_PATH nao configurado no .env')
    p = Path(raw)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parents[4] / p).resolve()
    return p


def _specs_dir() -> Path:
    return _sdd_root() / 'specs'


def _templates_dir() -> Path:
    return _sdd_root() / 'settings' / 'templates' / 'specs'


def _safe(base: Path, *parts: str) -> Path:
    target = (base.joinpath(*parts)).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(400, 'Caminho invalido')
    return target


def _slugify(text: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_only = nfkd.encode('ascii', 'ignore').decode('ascii')
    s = ascii_only.lower()
    s = re.sub(r'[^a-z0-9-]', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')


# ---------------------------------------------------------------------------
# Leitura de specs
# ---------------------------------------------------------------------------

@router.get('')
def listar_specs():
    specs_dir = _specs_dir()
    if not specs_dir.exists():
        return ok([])
    result = []
    for d in sorted(specs_dir.iterdir()):
        if not d.is_dir():
            continue
        arquivos = sorted(f.name for f in d.glob('*.md'))
        result.append({'slug': d.name, 'arquivos': arquivos})
    return ok(result)


@router.get('/exemplos')
def listar_exemplos():
    return listar_specs()


@router.get('/templates')
def listar_templates():
    tpl = _templates_dir()
    if not tpl.exists():
        return ok([])
    nomes = sorted({f.stem.split('.')[0] for f in tpl.glob('*.md')})
    return ok(nomes)


@router.get('/{feature}')
def get_spec(feature: str):
    specs_dir = _specs_dir()
    d = _safe(specs_dir, feature)
    if not d.exists():
        raise HTTPException(404, f'Feature "{feature}" nao encontrada')
    arquivos = {}
    for f in sorted(d.glob('*.md')):
        arquivos[f.stem] = f.read_text(encoding='utf-8')
    return ok({'slug': feature, 'arquivos': arquivos})


@router.get('/{feature}/{filename}')
def get_spec_file(feature: str, filename: str):
    if not filename.endswith('.md'):
        filename += '.md'
    specs_dir = _specs_dir()
    fp = _safe(specs_dir, feature, filename)
    if not fp.exists():
        raise HTTPException(404, f'{feature}/{filename} nao encontrado')
    return ok({'conteudo': fp.read_text(encoding='utf-8'), 'arquivo': filename, 'feature': feature})


# ---------------------------------------------------------------------------
# Criação de specs
# ---------------------------------------------------------------------------

class EspecCriar(BaseModel):
    slug: str
    titulo: str
    descricao: str = ''
    autor: str = ''
    exemplo_base: str | None = None
    templates: list[str] = ['requirements', 'design']


@router.post('')
def criar_spec(payload: EspecCriar):
    specs_dir = _specs_dir()
    slug = _slugify(payload.slug)
    if len(slug) < 2:
        raise HTTPException(400, 'Slug invalido ou muito curto')

    dest = _safe(specs_dir, slug)
    if dest.exists():
        raise HTTPException(409, f'Feature "{slug}" ja existe')

    dest.mkdir(parents=True)

    header = (
        f'<!--\n'
        f'  Feature   : {payload.titulo}\n'
        f'  Slug      : {slug}\n'
        f'  Criado em : {date.today()}\n'
        f'  Autor     : {payload.autor}\n'
        f'  Descricao : {payload.descricao}\n'
        f'-->\n\n'
    )

    criados = []

    if payload.exemplo_base:
        src = _safe(specs_dir, payload.exemplo_base)
        if not src.exists():
            raise HTTPException(404, f'Exemplo "{payload.exemplo_base}" nao encontrado')
        for src_file in sorted(src.glob('*.md')):
            content = src_file.read_text(encoding='utf-8')
            content = content.replace(payload.exemplo_base, slug)
            (dest / src_file.name).write_text(header + content, encoding='utf-8')
            criados.append(src_file.name)
    else:
        tpl_dir = _templates_dir()
        for tpl_name in payload.templates:
            tpl = tpl_dir / f'{tpl_name}.pt-br.md'
            if not tpl.exists():
                tpl = tpl_dir / f'{tpl_name}.md'
            if not tpl.exists():
                continue
            content = tpl.read_text(encoding='utf-8')
            (dest / f'{tpl_name}.md').write_text(header + content, encoding='utf-8')
            criados.append(f'{tpl_name}.md')

    return ok({'slug': slug, 'arquivos_criados': criados})


# ---------------------------------------------------------------------------
# Edição de specs
# ---------------------------------------------------------------------------

class EspecAtualizar(BaseModel):
    conteudo: str


@router.put('/{feature}/{filename}')
def atualizar_spec(feature: str, filename: str, payload: EspecAtualizar):
    if not filename.endswith('.md'):
        filename += '.md'
    specs_dir = _specs_dir()
    fp = _safe(specs_dir, feature, filename)
    if not fp.exists():
        raise HTTPException(404, f'{feature}/{filename} nao encontrado')
    fp.write_text(payload.conteudo, encoding='utf-8')
    return ok({'arquivo': filename, 'feature': feature})
