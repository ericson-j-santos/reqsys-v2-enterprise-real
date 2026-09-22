from base64 import b64encode
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.certificate_auth import reset_challenges

client = TestClient(app)


def _gerar_certificado_teste():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'Usuario Certificado'),
        x509.NameAttribute(NameOID.EMAIL_ADDRESS, 'cert.user@example.com'),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
    return key, cert_pem


def test_config_expoe_certificate_enabled():
    original = settings.certificate_login_enabled
    settings.certificate_login_enabled = True
    try:
        r = client.get('/v1/auth/config')
        assert r.status_code == 200
        assert r.json()['data']['certificate_enabled'] is True
    finally:
        settings.certificate_login_enabled = original


def test_certificate_challenge_desligado_retorna_503():
    original = settings.certificate_login_enabled
    settings.certificate_login_enabled = False
    try:
        r = client.post('/v1/auth/certificate/challenge')
        assert r.status_code == 503
    finally:
        settings.certificate_login_enabled = original


def test_certificate_login_valido_emite_token():
    original_enabled = settings.certificate_login_enabled
    original_trust_store = settings.certificate_trust_store_path
    original_allowed_issuers = settings.certificate_allowed_issuers
    settings.certificate_login_enabled = True
    settings.certificate_trust_store_path = ''
    settings.certificate_allowed_issuers = ''
    reset_challenges()
    try:
        key, cert_pem = _gerar_certificado_teste()
        challenge_response = client.post('/v1/auth/certificate/challenge')
        challenge = challenge_response.json()['data']['challenge']
        signature = key.sign(challenge.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256())

        r = client.post('/v1/auth/certificate/verify', json={
            'certificate_pem': cert_pem,
            'challenge': challenge,
            'signature_base64': b64encode(signature).decode('ascii'),
        })

        assert r.status_code == 200
        data = r.json()['data']
        assert data['access_token']
        assert data['usuario']['auth_provider'] == 'certificate'
        assert data['usuario']['email'] == 'cert.user@example.com'
    finally:
        reset_challenges()
        settings.certificate_login_enabled = original_enabled
        settings.certificate_trust_store_path = original_trust_store
        settings.certificate_allowed_issuers = original_allowed_issuers


def test_certificate_desafio_nao_pode_ser_reutilizado():
    original_enabled = settings.certificate_login_enabled
    settings.certificate_login_enabled = True
    reset_challenges()
    try:
        key, cert_pem = _gerar_certificado_teste()
        challenge = client.post('/v1/auth/certificate/challenge').json()['data']['challenge']
        signature = b64encode(key.sign(challenge.encode('utf-8'), padding.PKCS1v15(), hashes.SHA256())).decode('ascii')
        payload = {'certificate_pem': cert_pem, 'challenge': challenge, 'signature_base64': signature}

        assert client.post('/v1/auth/certificate/verify', json=payload).status_code == 200
        assert client.post('/v1/auth/certificate/verify', json=payload).status_code == 401
    finally:
        reset_challenges()
        settings.certificate_login_enabled = original_enabled


def test_producao_com_certificado_exige_trust_store():
    original_env = settings.app_environment
    original_demo = settings.allow_demo_login
    original_jwt_secret = settings.jwt_secret
    original_issuer = settings.jwt_issuer
    original_audience = settings.jwt_audience
    original_tenant = settings.azure_tenant_id
    original_client = settings.azure_client_id
    original_cert_enabled = settings.certificate_login_enabled
    original_trust_store = settings.certificate_trust_store_path

    settings.app_environment = 'production'
    settings.allow_demo_login = False
    settings.jwt_secret = 'segredo-forte-para-testes-com-mais-de-32-caracteres'
    settings.jwt_issuer = 'reqsys-test'
    settings.jwt_audience = 'reqsys-users'
    settings.azure_tenant_id = 'tenant-teste'
    settings.azure_client_id = 'client-teste'
    settings.certificate_login_enabled = True
    settings.certificate_trust_store_path = ''
    try:
        try:
            settings.validate_production_gates()
            assert False, 'validate_production_gates deveria falhar'
        except RuntimeError as exc:
            assert 'CERT_TRUST_STORE_PATH' in str(exc)
    finally:
        settings.app_environment = original_env
        settings.allow_demo_login = original_demo
        settings.jwt_secret = original_jwt_secret
        settings.jwt_issuer = original_issuer
        settings.jwt_audience = original_audience
        settings.azure_tenant_id = original_tenant
        settings.azure_client_id = original_client
        settings.certificate_login_enabled = original_cert_enabled
        settings.certificate_trust_store_path = original_trust_store
