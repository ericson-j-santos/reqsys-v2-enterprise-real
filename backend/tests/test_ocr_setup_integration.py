"""
Testes de integração OCR v2 — Setup e readiness

Valida:
- Configuração de chaves de criptografia
- Readiness endpoint
- Integridade de dados criptografados
- Segurança: sem plaintext PII no banco
- Rotação de chaves
"""

import os
import base64
import pytest

from app.ocr.storage import (
    OcrDataProtector,
    OcrResultadoPersistido,
    RepositorioResultadosOcrSqlAlchemy,
)
from app.ocr.worker import OcrResultado


class TestOcrSetupConfiguration:
    """Validar configuração de setup do OCR"""

    def test_ocr_encryption_key_exists(self):
        """OCR_DATA_ENCRYPTION_KEY deve estar configurada"""
        key = os.getenv("OCR_DATA_ENCRYPTION_KEY")
        assert key is not None, "❌ OCR_DATA_ENCRYPTION_KEY não configurada"
        assert len(key) > 0, "❌ OCR_DATA_ENCRYPTION_KEY está vazia"

    def test_ocr_encryption_key_is_valid_base64(self):
        """Chave deve ser Base64 válido"""
        key = os.getenv("OCR_DATA_ENCRYPTION_KEY")

        try:
            decoded = base64.b64decode(key, validate=True)
            assert len(decoded) == 32, f"❌ Chave tem {len(decoded)} bytes, esperado 32"
        except Exception as e:
            pytest.fail(f"❌ Chave inválida em Base64: {e}")

    def test_ocr_input_root_configured(self):
        """OCR_INPUT_ROOT deve estar configurada e acessível"""
        input_root = os.getenv("OCR_INPUT_ROOT")
        assert input_root is not None, "❌ OCR_INPUT_ROOT não configurada"

        # Não validar existência do diretório aqui
        # (pode estar em volume Docker não montado)
        assert len(input_root) > 0, "❌ OCR_INPUT_ROOT está vazia"

    def test_ocr_key_version_configured(self):
        """OCR_DATA_KEY_VERSION deve estar configurada"""
        version = os.getenv("OCR_DATA_KEY_VERSION", "v1")
        assert version in ["v1", "v2", "v3"], f"❌ Versão inválida: {version}"
        assert version == "v1", "⚠️ Versão esperada: v1 (rotação não ativa ainda)"


class TestOcrReadinessEndpoint:
    """Validar endpoint /v1/ocr/readiness"""

    def test_readiness_returns_200(self, client):
        """GET /v1/ocr/readiness deve retornar HTTP 200"""
        response = client.get("/v1/ocr/readiness")
        assert response.status_code == 200, f"❌ Status: {response.status_code}"

    def test_readiness_response_structure(self, client):
        """Resposta deve ter estrutura válida"""
        response = client.get("/v1/ocr/readiness")
        data = response.json()

        required_fields = [
            "ready",
            "encryption",
            "key_configured",
            "input_root_configured",
            "plaintext_storage_allowed",
        ]

        for field in required_fields:
            assert field in data, f"❌ Campo faltando: {field}"

    def test_readiness_ready_is_true(self, client):
        """readiness.ready deve ser true após setup correto"""
        response = client.get("/v1/ocr/readiness")
        data = response.json()

        assert data["ready"] is True, (
            f"❌ OCR não pronto. Status: {data}\n"
            f"   Verifique: OCR_DATA_ENCRYPTION_KEY, OCR_INPUT_ROOT"
        )

    def test_readiness_encryption_type(self, client):
        """Tipo de criptografia deve ser AES-256-GCM"""
        response = client.get("/v1/ocr/readiness")
        data = response.json()

        assert data["encryption"] == "AES-256-GCM", (
            f"❌ Criptografia esperada: AES-256-GCM, recebida: {data['encryption']}"
        )

    def test_readiness_key_configured(self, client):
        """key_configured deve ser true"""
        response = client.get("/v1/ocr/readiness")
        data = response.json()

        assert data["key_configured"] is True, (
            "❌ Chave não configurada. "
            "Verifique OCR_DATA_ENCRYPTION_KEY em .env ou secrets"
        )

    def test_readiness_input_root_configured(self, client):
        """input_root_configured deve ser true"""
        response = client.get("/v1/ocr/readiness")
        data = response.json()

        assert data["input_root_configured"] is True, (
            "❌ OCR_INPUT_ROOT não configurado. "
            "Crie diretório e configure variável de ambiente"
        )

    def test_readiness_no_plaintext_storage_allowed(self, client):
        """plaintext_storage_allowed DEVE ser false (fail-closed)"""
        response = client.get("/v1/ocr/readiness")
        data = response.json()

        assert data["plaintext_storage_allowed"] is False, (
            "🚨 CRÍTICO: Storage em plaintext está ativo! "
            "OCR deve armazenar dados criptografados apenas."
        )


class TestOcrEncryption:
    """Validar implementação de criptografia"""

    def test_encryption_key_not_empty(self):
        """Chave de criptografia não deve estar vazia"""
        key = os.getenv("OCR_DATA_ENCRYPTION_KEY")
        assert key and len(key) > 0, "❌ Chave vazia"

    def test_ocr_data_protector_initializes(self):
        """OcrDataProtector deve inicializar sem erro"""
        try:
            protector = OcrDataProtector()
            assert protector is not None
        except Exception as e:
            pytest.fail(f"❌ Erro ao inicializar OcrDataProtector: {e}")

    def test_encryption_decrypt_roundtrip(self):
        """Proteger e revelar deve retornar o payload original"""
        protector = OcrDataProtector()
        payload = {"valor": "Teste de criptografia OCR", "motivos": ["teste"]}
        aad = "test-001"

        encrypted = protector.proteger(payload, aad=aad)
        decrypted = protector.revelar(encrypted, aad=aad)

        assert decrypted == payload, (
            f"❌ Roundtrip falhou. "
            f"Original: {payload}, Decriptado: {decrypted}"
        )

    def test_encryption_different_keys_cannot_decrypt(self):
        """Rotação de chave ainda não tem cenário multi-chave implementado"""
        pytest.skip("Cenário multi-chave ainda não implementado; não declarar validação falsa")


class TestOcrDatabaseSecurity:
    """Validar segurança dos dados no banco"""

    def test_no_plaintext_pii_in_database(self, db_session):
        """Persistir resultado deve gravar somente payload protegido no banco"""
        marker = "PII-TESTE-NUNCA-EM-PLAIN-TEXT"
        job_id = "security-storage-test-001"
        repository = RepositorioResultadosOcrSqlAlchemy()
        repository.salvar(
            OcrResultado(
                job_id=job_id,
                correlation_id="security-storage-correlation",
                tipo_documento="TESTE",
                campo="nome",
                estado_ocr="REVISAO",
                confianca=0.91,
                valor=marker,
                motivos=("teste-seguranca",),
            )
        )

        db_session.expire_all()
        stored = (
            db_session.query(OcrResultadoPersistido)
            .filter(OcrResultadoPersistido.job_id == job_id)
            .one()
        )

        assert stored.payload_protegido, "❌ Payload criptografado não foi persistido"
        assert marker not in stored.payload_protegido, "🚨 PII persistida em plaintext"

        revealed = repository.obter(job_id, revelar_pii=True)
        assert revealed is not None
        assert revealed["valor"] == marker, "❌ Payload protegido não pôde ser validado"

    def test_encrypted_payload_is_not_empty(self, db_session):
        """Payloads criptografados não devem estar vazios"""
        encrypted_results = db_session.query(
            OcrResultadoPersistido
        ).filter(
            OcrResultadoPersistido.payload_protegido.isnot(None),
        ).limit(5).all()

        for result in encrypted_results:
            assert len(result.payload_protegido) > 0, (
                f"❌ Payload criptografado vazio para job {result.job_id}"
            )

    def test_reviewer_identity_is_hashed(self, db_session):
        """Identidade do revisor deve estar hasheada, não em plaintext"""
        pytest.skip("Cenário de decisão do revisor não faz parte deste setup; não declarar validação falsa")


class TestOcrKeyRotation:
    """Validar metadados atuais de chave sem simular rotação inexistente"""

    def test_key_rotation_support(self):
        """Rotação multi-chave ainda não está implementada"""
        pytest.skip("Rotação multi-chave ainda não implementada; não declarar capacidade inexistente")

    def test_key_version_parameter(self):
        """Protector deve usar OCR_DATA_KEY_VERSION configurada"""
        version = os.getenv("OCR_DATA_KEY_VERSION")
        assert version is not None, "❌ OCR_DATA_KEY_VERSION não configurada"
        protector = OcrDataProtector()
        assert protector.key_version == version, (
            f"❌ Versão ativa divergente: esperado {version}, obtido {protector.key_version}"
        )

    def test_old_keys_can_still_decrypt(self):
        """Compatibilidade de chave antiga depende de suporte multi-chave futuro"""
        pytest.skip("Compatibilidade v1→v2 ainda não implementada; não declarar validação falsa")


class TestOcrWorkflowIntegration:
    """Validar fluxo end-to-end"""

    def test_readiness_before_processing(self, client):
        """Verificar readiness antes de qualquer processamento"""
        response = client.get("/v1/ocr/readiness")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    def test_job_creation_requires_ready_state(self, client, auth_token):
        """Criar job OCR deve falhar se readiness = false"""
        pytest.skip("Cenário negativo de criação de job ainda não implementado; não declarar validação falsa")

    def test_ocr_result_encryption_in_workflow(self, db_session):
        """Resultado de OCR deve estar criptografado após processamento"""
        pytest.skip("E2E de processamento OCR ainda não implementado neste arquivo; não declarar validação falsa")


class TestOcrErrorHandling:
    """Validar tratamento de erros"""

    def test_missing_encryption_key_raises_error(self):
        """Inicializar sem chave deve falhar"""
        # Temporariamente remover chave
        old_key = os.environ.pop("OCR_DATA_ENCRYPTION_KEY", None)

        try:
            with pytest.raises(Exception):
                OcrDataProtector()
        finally:
            # Restaurar chave
            if old_key:
                os.environ["OCR_DATA_ENCRYPTION_KEY"] = old_key

    def test_invalid_encryption_key_raises_error(self):
        """Chave inválida deve gerar erro"""
        # Temporariamente usar chave inválida
        old_key = os.environ.get("OCR_DATA_ENCRYPTION_KEY")
        os.environ["OCR_DATA_ENCRYPTION_KEY"] = "invalid-base64-!!!"

        try:
            with pytest.raises(Exception):
                OcrDataProtector()
        finally:
            if old_key:
                os.environ["OCR_DATA_ENCRYPTION_KEY"] = old_key


class TestOcrMetrics:
    """Validar métricas e observabilidade"""

    def test_readiness_metric_available(self):
        """Métrica ocr_readiness_status deve estar disponível"""
        pytest.skip("Validação Prometheus ainda não implementada; não declarar validação falsa")

    def test_ocr_jobs_processed_metric(self):
        """Métrica de jobs processados deve estar disponível"""
        pytest.skip("Validação de jobs processados ainda não implementada; não declarar validação falsa")


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Cliente HTTP para testes"""
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def db_session():
    """Sessão do banco para testes"""
    from app.db import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def auth_token():
    """Token JWT para testes autenticados"""
    # Gerar token válido para ambiente de teste
    from datetime import datetime, timedelta
    import jwt

    secret = os.getenv("JWT_SECRET", "test-secret")
    payload = {
        "sub": "test-user",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token
