"""Testes da validação semântica de identificadores documentais.

Controles contra falso positivo aplicados aqui:

- o dígito verificador de CPF é conferido contra uma implementação de
  referência escrita de forma independente (não reaproveita o módulo);
- vetores válidos sofrem mutação de dígito e devem ser recusados;
- cada estado "válido" é testado junto do seu par negativo.
"""
from __future__ import annotations

import sys
from hashlib import sha256
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ocr import identificadores_documentais as mod

# CPF publicamente usado como exemplo de dígito verificador válido.
CPF_VALIDO = '52998224725'


def _dv_cpf_referencia(base: str) -> str:
    """Implementação independente do módulo, para cruzar o resultado."""
    def digito(parcial: str) -> str:
        pesos = range(len(parcial) + 1, 1, -1)
        soma = sum(int(d) * p for d, p in zip(parcial, pesos))
        resto = 11 - (soma % 11)
        return '0' if resto > 9 else str(resto)

    primeiro = digito(base[:9])
    return primeiro + digito(base[:9] + primeiro)


def _cpfs_de_amostra() -> list[str]:
    bases = [f'{n:09d}' for n in range(10_000_000, 10_000_050)]
    bases += ['529982247', '123456789', '987654321']
    return [base + _dv_cpf_referencia(base) for base in bases]


# --------------------------------------------------------------------------
# Dígito verificador
# --------------------------------------------------------------------------


def test_cpf_valido_de_vetor_conhecido():
    assert mod.validar_cpf(CPF_VALIDO) is True


def test_cpf_confere_com_implementacao_de_referencia_independente():
    for cpf in _cpfs_de_amostra():
        assert mod.validar_cpf(cpf) is True, cpf
        assert mod._dv_cpf(cpf[:9]) == _dv_cpf_referencia(cpf[:9])


def test_cpf_rejeita_mutacao_de_qualquer_digito():
    """O teste do teste: um vetor válido mutado precisa falhar."""
    for posicao in range(11):
        original = int(CPF_VALIDO[posicao])
        mutado = CPF_VALIDO[:posicao] + str((original + 1) % 10) + CPF_VALIDO[posicao + 1:]
        assert mod.validar_cpf(mutado) is False, f'mutação em {posicao} passou'


def test_cpf_rejeita_sequencias_repetidas():
    for digito in '0123456789':
        assert mod.validar_cpf(digito * 11) is False


@pytest.mark.parametrize('entrada', ['', '123', '5299822472', '5299822472X', '529982247250'])
def test_cpf_rejeita_formatos_invalidos(entrada):
    assert mod.validar_cpf(entrada) is False


def test_cnh_valida_gerada_pelo_algoritmo_denatran():
    determinadas = 0
    for n in range(0, 20_000, 7):
        base = f'{n:09d}'
        dv = mod._dv_cnh(base)
        if dv is None or len(set(base + dv)) == 1:
            continue
        determinadas += 1
        assert mod.validar_cnh(base + dv) is True, base + dv
    assert determinadas > 1_000, 'amostra insuficiente de CNH determinadas'


def test_cnh_rejeita_mutacao_de_qualquer_digito():
    cnh = '052192401' + mod._dv_cnh('052192401')
    for posicao in range(11):
        original = int(cnh[posicao])
        mutado = cnh[:posicao] + str((original + 1) % 10) + cnh[posicao + 1:]
        assert mod.validar_cnh(mutado) is not True, f'mutação em {posicao} passou'


def test_cnh_rejeita_sequencias_repetidas():
    for digito in '0123456789':
        assert mod.validar_cnh(digito * 11) is False


def test_cnh_nunca_produz_digito_verificador_fora_da_faixa():
    """Ou dois dígitos determinados, ou indeterminado — nunca um valor inválido."""
    for n in range(0, 1_000_000, 97):
        dv = mod._dv_cnh(f'{n:09d}')
        assert dv is None or (len(dv) == 2 and dv.isdigit()), (n, dv)


def test_cnh_com_verificador_indeterminado_nao_e_declarada_valida():
    """O ramo ambíguo do algoritmo não pode virar VALIDO nem INVALIDO."""
    indeterminadas = [
        f'{n:09d}' for n in range(0, 2_000_000)
        if mod._dv_cnh(f'{n:09d}') is None
    ][:3]
    assert indeterminadas, 'ramo indeterminado não exercitado'
    for base in indeterminadas:
        assert mod.validar_cnh(base + '00') is None
        [item] = mod.detectar_identificadores(f'CNH REGISTRO {base}00')
        assert item.estado == mod.ESTADO_VALIDACAO_INDISPONIVEL
        assert item.confiavel is False


# --------------------------------------------------------------------------
# Detecção ancorada em rótulo
# --------------------------------------------------------------------------


def test_detecta_cpf_valido_com_rotulo():
    [item] = mod.detectar_identificadores('CPF: 529.982.247-25')
    assert item.tipo == mod.TIPO_CPF
    assert item.estado == mod.ESTADO_VALIDO
    assert item.confiavel is True


def test_detecta_cpf_invalido_como_invalido():
    [item] = mod.detectar_identificadores('CPF 000.000.000-00')
    assert item.estado == mod.ESTADO_INVALIDO
    assert item.confiavel is False


def test_sem_rotulo_nao_ha_deteccao():
    """Fail-closed: número solto em texto corrido não vira identificador."""
    assert mod.detectar_identificadores('Total de 529982247 25 reais pagos') == []


def test_numero_distante_do_rotulo_nao_e_capturado():
    texto = 'CPF do titular consta no verso do documento anexo 529.982.247-25'
    assert mod.detectar_identificadores(texto) == []


def test_rg_nunca_e_declarado_valido():
    """RG é estadual: afirmar validade seria fabricar evidência."""
    [item] = mod.detectar_identificadores('RG: 12.345.678-9')
    assert item.tipo == mod.TIPO_RG
    assert item.estado == mod.ESTADO_VALIDACAO_INDISPONIVEL
    assert item.confiavel is False


def test_cin_e_verificada_pelo_digito_do_cpf():
    """A CIN adota o número do CPF (Decreto 10.977/2022)."""
    [valido] = mod.detectar_identificadores('Identidade Nacional (CIN): 529.982.247-25')
    assert valido.tipo == mod.TIPO_CIN
    assert valido.estado == mod.ESTADO_VALIDO

    [invalido] = mod.detectar_identificadores('CIN: 529.982.247-26')
    assert invalido.estado == mod.ESTADO_INVALIDO


def test_cnh_detectada_por_rotulo_de_registro():
    cnh = '052192401' + mod._dv_cnh('052192401')
    [item] = mod.detectar_identificadores(f'CNH REGISTRO {cnh}')
    assert item.tipo == mod.TIPO_CNH
    assert item.estado == mod.ESTADO_VALIDO


def test_correcao_de_ocr_nao_e_promovida_a_valido():
    """Confusão de OCR corrigida vira estado próprio, nunca VALIDO puro."""
    [item] = mod.detectar_identificadores('CPF: S29.982.247-25')
    assert item.estado == mod.ESTADO_VALIDO_APOS_CORRECAO_OCR
    assert item.estado != mod.ESTADO_VALIDO
    assert item.correcoes_ocr == 1


def test_correcao_de_ocr_nao_salva_numero_realmente_invalido():
    """A correção recupera o comprimento do campo, mas não o verificador."""
    [item] = mod.detectar_identificadores('CPF: S29.982.247-26')
    assert item.estado == mod.ESTADO_INVALIDO
    assert item.confiavel is False


def test_formato_inesperado_quando_faltam_digitos():
    [item] = mod.detectar_identificadores('CPF: 529.982-25')
    assert item.estado == mod.ESTADO_FORMATO_INESPERADO


@pytest.mark.parametrize('texto', ['', '   ', 'documento sem identificador algum'])
def test_texto_sem_identificador_retorna_lista_vazia(texto):
    assert mod.detectar_identificadores(texto) == []


def test_multiplos_identificadores_na_mesma_pagina():
    texto = 'C.P.F. nº 529.982.247-25\nRG: 12.345.678-9'
    itens = mod.detectar_identificadores(texto)
    assert {item.tipo for item in itens} == {mod.TIPO_CPF, mod.TIPO_RG}


def test_ocorrencia_duplicada_na_mesma_pagina_e_deduplicada():
    texto = 'CPF: 529.982.247-25 e novamente CPF: 529.982.247-25'
    assert len(mod.detectar_identificadores(texto)) == 1


def test_paginas_preservam_origem():
    cnh = '052192401' + mod._dv_cnh('052192401')
    itens = mod.detectar_identificadores_por_paginas(
        [(1, 'CPF: 529.982.247-25', 0.91), (2, f'CNH: {cnh}', 0.78)]
    )
    assert [(item.pagina, item.tipo) for item in itens] == [
        (1, mod.TIPO_CPF),
        (2, mod.TIPO_CNH),
    ]
    assert itens[1].confianca_ocr == pytest.approx(0.78)


# --------------------------------------------------------------------------
# Política: revisão humana e não exposição de PII
# --------------------------------------------------------------------------


def test_identificador_sempre_exige_revisao_humana():
    [item] = mod.detectar_identificadores('CPF: 529.982.247-25')
    assert item.requer_validacao_humana is True


def test_nao_e_possivel_construir_identificador_dispensando_revisao():
    with pytest.raises(ValueError):
        mod.IdentificadorDocumental(
            tipo=mod.TIPO_CPF,
            estado=mod.ESTADO_VALIDO,
            rotulo='CPF',
            mascara='***.***.***-25',
            fingerprint='f' * 64,
            fingerprint_escopo=mod.ESCOPO_FINGERPRINT_EFEMERO,
            digitos=11,
            correcoes_ocr=0,
            requer_validacao_humana=False,
        )


def test_mascara_nao_revela_o_identificador():
    [item] = mod.detectar_identificadores('CPF: 529.982.247-25')
    assert item.mascara == '***.***.***-25'
    assert '529' not in item.mascara
    assert '982' not in item.mascara


def test_evidencia_publicavel_nao_carrega_mascara_nem_texto():
    [item] = mod.detectar_identificadores('CPF: 529.982.247-25')
    evidencia = item.para_evidencia()
    assert 'mascara' not in evidencia
    assert 'texto' not in evidencia
    serializado = str(evidencia)
    for fragmento in ('529', '982', '247', '25'):
        assert fragmento not in serializado.replace(evidencia['fingerprint'], '')


def test_fingerprint_usa_chave_e_nao_e_sha256_puro():
    """SHA-256 sem chave sobre 11 dígitos é reversível por força bruta."""
    chave = b'chave-de-teste'
    [item] = mod.detectar_identificadores('CPF: 529.982.247-25', chave_fingerprint=chave)
    assert item.fingerprint != sha256(f'CPF:{CPF_VALIDO}'.encode()).hexdigest()
    assert item.fingerprint_escopo == mod.ESCOPO_FINGERPRINT_PERSISTENTE


def test_fingerprint_e_estavel_para_a_mesma_chave_e_muda_com_outra():
    chave_a, chave_b = b'chave-a', b'chave-b'
    texto = 'CPF: 529.982.247-25'
    [primeiro] = mod.detectar_identificadores(texto, chave_fingerprint=chave_a)
    [repetido] = mod.detectar_identificadores(texto, chave_fingerprint=chave_a)
    [outro] = mod.detectar_identificadores(texto, chave_fingerprint=chave_b)
    assert primeiro.fingerprint == repetido.fingerprint
    assert primeiro.fingerprint != outro.fingerprint


def test_chave_de_ambiente_produz_escopo_persistente(monkeypatch):
    monkeypatch.setenv(mod.ENV_CHAVE_FINGERPRINT, 'chave-de-ambiente')
    [item] = mod.detectar_identificadores('CPF: 529.982.247-25')
    assert item.fingerprint_escopo == mod.ESCOPO_FINGERPRINT_PERSISTENTE


def test_sem_chave_configurada_o_escopo_e_efemero(monkeypatch):
    monkeypatch.delenv(mod.ENV_CHAVE_FINGERPRINT, raising=False)
    [item] = mod.detectar_identificadores('CPF: 529.982.247-25')
    assert item.fingerprint_escopo == mod.ESCOPO_FINGERPRINT_EFEMERO


# --------------------------------------------------------------------------
# Evidência agregada
# --------------------------------------------------------------------------


def test_resumo_de_evidencia_agrega_sem_dado_pessoal():
    itens = mod.detectar_identificadores_por_paginas(
        [(1, 'CPF: 529.982.247-25', 0.9), (2, 'RG: 12.345.678-9', 0.8)]
    )
    resumo = mod.resumo_evidencia(itens)
    assert resumo['total'] == 2
    assert resumo['por_tipo'] == {mod.TIPO_CPF: 1, mod.TIPO_RG: 1}
    assert resumo['por_estado'] == {
        mod.ESTADO_VALIDO: 1,
        mod.ESTADO_VALIDACAO_INDISPONIVEL: 1,
    }
    assert resumo['confiaveis'] == 1
    assert resumo['todos_exigem_revisao_humana'] is True
    assert resumo['contem_dado_pessoal'] is False


def test_resumo_de_evidencia_vazio():
    resumo = mod.resumo_evidencia([])
    assert resumo['total'] == 0
    assert resumo['confiaveis'] == 0
    assert resumo['todos_exigem_revisao_humana'] is True


def test_limite_de_identificadores_por_pagina():
    texto = '\n'.join(f'CPF: 529.982.247-25 linha {i}' for i in range(600))
    assert len(mod.detectar_identificadores(texto)) <= mod._MAX_IDENTIFICADORES
