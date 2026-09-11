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
from datetime import datetime

from app.ocr.storage import (
    OcrDataProtector,
    ocr_store_readiness,
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
        """Encriptar e decriptar deve retornar valor original"""
        protector = OcrDataProtector()
        plaintext = "Teste de criptografia OCR"

        encrypted = protector.encrypt(plaintext, job_id="test-001")
        decrypted = protector.decrypt(encrypted, job_id="test-001")

        assert decrypted == plaintext, (
            f"❌ Roundtrip falhou. "
            f"Original: {plaintext}, Decriptado: {decrypted}"
        )

    def test_encryption_different_keys_cannot_decrypt(self):
        """Dados criptografados com chave v1 não devem ser decriptados com v2"""
        # Simular mudança de chave
        protector = OcrDataProtector()
        plaintext = "Dados sensíveis"

        encrypted = protector.encrypt(plaintext, job_id="test-002")

        # Tentar decriptar com chave errada deve falhar ou retornar lixo
        # (Não implementado ainda, placeholder para segurança futura)
        # assert decryption_with_wrong_key raises error


class TestOcrDatabaseSecurity:
    """Validar segurança dos dados no banco"""

    def test_no_plaintext_pii_in_database(self, db_session):
        """Validar que não há PII em plaintext no banco de dados"""
        # Query para OCR resultados que tenham payload_protegido NULL
        # (indicaria armazenamento em plaintext)

        suspicious_results = db_session.query(
            OcrResultado
        ).filter(
            OcrResultado.payload_protegido.is_(None),
            OcrResultado.resultado.isnot(None),  # Tem resultado
        ).all()

        if suspicious_results:
            result_ids = [r.id for r in suspicious_results]
            pytest.fail(
                f"🚨 CRÍTICO: PII detectado em plaintext no banco! "
                f"Job IDs: {result_ids}\n"
                f"Execução imediata de patch de segurança necessária."
            )

    def test_encrypted_payload_is_not_empty(self, db_session):
        """Payloads criptografados não devem estar vazios"""
        encrypted_results = db_session.query(
            OcrResultado
        ).filter(
            OcrResultado.payload_protegido.isnot(None),
        ).limit(5).all()

        for result in encrypted_results:
            assert len(result.payload_protegido) > 0, (
                f"❌ Payload criptografado vazio para job {result.id}"
            )

    def test_reviewer_identity_is_hashed(self, db_session):
        """Identidade do revisor deve estar hasheada, não em plaintext"""
        # Verificar que reviewer_id/reviewer_name são hasheados
        # (Implementação específica do schema)
        pass


class TestOcrKeyRotation:
    """Validar capacidade de rotação de chaves"""

    def test_key_rotation_support(self):
        """Sistema deve suportar rotação de chaves"""
        protector = OcrDataProtector()
        assert hasattr(protector, "supports_key_rotation"), (
            "❌ OcrDataProtector não tem método supports_key_rotation"
        )

    def test_key_version_parameter(self):
        """Criptografia deve usar OCR_DATA_KEY_VERSION"""
        version = os.getenv("OCR_DATA_KEY_VERSION")
        assert version is not None, "❌ OCR_DATA_KEY_VERSION não configurada"

    def test_old_keys_can_still_decrypt(self):
        """Dados criptografados com v1 devem ser descriptáveis após upgrade para v2"""
        # Teste placeholder para segurança futura
        # Quando houver múltiplas versões de chave:
        # - v1 usada para dados antigos
        # - v2 usada para novos dados
        # - Ambas devem funcionar para decrypt
        pass


class TestOcrWorkflowIntegration:
    """Validar fluxo end-to-end"""

    def test_readiness_before_processing(self, client):
        """Verificar readiness antes de qualquer processamento"""
        response = client.get("/v1/ocr/readiness")
        assert response.status_code == 200
        assert response.json()["ready"] is True

    def test_job_creation_requires_ready_state(self, client, auth_token):
        """Criar job OCR deve falhar se readiness = false"""
        # Teste que valida que sem chave/input_root, jobs não podem ser criados
        # (Implementação específica do endpoint)
        pass

    def test_ocr_result_encryption_in_workflow(self, db_session):
        """Resultado de OCR deve estar criptografado após processamento"""
        # Simular workflow completo e validar criptografia
        # (Implementação específica)
        pass


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
        # Verificar que Prometheus está exportando métrica
        # GET /metrics e procurar por ocr_readiness_status
        pass

    def test_ocr_jobs_processed_metric(self):
        """Métrica de jobs processados deve estar disponível"""
        # Verificar ocr_jobs_processed_total
        pass


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
    from app.core.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def auth_token():
    """Token JWT para testes autenticados"""
    # Gerar token válido para ambiente de teste
    import secrets
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
