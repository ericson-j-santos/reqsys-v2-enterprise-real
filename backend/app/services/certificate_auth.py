import base64
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtensionOID, NameOID


class CertificateAuthError(ValueError):
    pass


@dataclass(frozen=True)
class CertificateIdentity:
    subject: str
    issuer: str
    serial_number: str
    common_name: str
    email: str
    cpf: str
    cnpj: str

    @property
    def stable_identifier(self) -> str:
        return self.email or self.cpf or self.cnpj or self.serial_number

    @property
    def display_name(self) -> str:
        return self.common_name or self.email or self.stable_identifier

    @property
    def reqsys_email(self) -> str:
        if self.email:
            return self.email
        local = self.cpf or self.cnpj or self.serial_number[-16:]
        return f'certificado-{local}@reqsys.local'


_challenges: dict[str, float] = {}


def criar_desafio(ttl_seconds: int) -> dict:
    challenge = secrets.token_urlsafe(48)
    expires_at = time.time() + max(30, ttl_seconds)
    _challenges[challenge] = expires_at
    _limpar_expirados()
    return {'challenge': challenge, 'expires_in': ttl_seconds}


def validar_login_certificado(
    *,
    certificate_pem: str,
    challenge: str,
    signature_base64: str,
    allowed_issuers: str = '',
    trust_store_path: str = '',
) -> CertificateIdentity:
    _consumir_desafio(challenge)
    cert = _load_certificate(certificate_pem)
    _validar_periodo(cert)
    _validar_issuer_permitido(cert, allowed_issuers)
    _validar_trust_store(cert, trust_store_path)
    _validar_assinatura(cert, challenge.encode('utf-8'), signature_base64)
    return _extrair_identidade(cert)


def reset_challenges() -> None:
    _challenges.clear()


def _limpar_expirados() -> None:
    now = time.time()
    expirados = [valor for valor, expira_em in _challenges.items() if expira_em <= now]
    for valor in expirados:
        _challenges.pop(valor, None)


def _consumir_desafio(challenge: str) -> None:
    _limpar_expirados()
    expires_at = _challenges.pop(challenge, None)
    if not expires_at:
        raise CertificateAuthError('Desafio invalido ou expirado')


def _load_certificate(certificate_pem: str) -> x509.Certificate:
    data = certificate_pem.encode('utf-8')
    try:
        if b'-----BEGIN CERTIFICATE-----' in data:
            return x509.load_pem_x509_certificate(data)
        return x509.load_der_x509_certificate(base64.b64decode(certificate_pem))
    except Exception as exc:
        raise CertificateAuthError('Certificado invalido') from exc


def _validar_periodo(cert: x509.Certificate) -> None:
    now = time.time()
    not_before = cert.not_valid_before_utc.timestamp()
    not_after = cert.not_valid_after_utc.timestamp()
    if now < not_before or now > not_after:
        raise CertificateAuthError('Certificado fora do periodo de validade')


def _validar_issuer_permitido(cert: x509.Certificate, allowed_issuers: str) -> None:
    issuers = [item.strip() for item in allowed_issuers.split(',') if item.strip()]
    if not issuers:
        return
    issuer_text = cert.issuer.rfc4514_string()
    if not any(issuer in issuer_text for issuer in issuers):
        raise CertificateAuthError('Emissor do certificado nao permitido')


def _validar_trust_store(cert: x509.Certificate, trust_store_path: str) -> None:
    if not trust_store_path:
        return

    path = Path(trust_store_path)
    if not path.exists():
        raise CertificateAuthError('Trust store de certificados nao encontrada')

    trusted_certs = _load_trust_store(path)
    if not trusted_certs:
        raise CertificateAuthError('Trust store de certificados vazia')

    for issuer_cert in trusted_certs:
        if issuer_cert.subject != cert.issuer:
            continue
        try:
            public_key = issuer_cert.public_key()
            signature_hash = cert.signature_hash_algorithm
            if isinstance(public_key, rsa.RSAPublicKey):
                public_key.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), signature_hash)
            elif isinstance(public_key, ec.EllipticCurvePublicKey):
                public_key.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(signature_hash))
            else:
                continue
            return
        except InvalidSignature:
            continue

    raise CertificateAuthError('Cadeia do certificado nao confiavel')


def _load_trust_store(path: Path) -> list[x509.Certificate]:
    files = [path] if path.is_file() else list(path.glob('*.pem')) + list(path.glob('*.crt'))
    certs: list[x509.Certificate] = []
    for file_path in files:
        data = file_path.read_bytes()
        if b'-----BEGIN CERTIFICATE-----' in data:
            chunks = data.split(b'-----END CERTIFICATE-----')
            for chunk in chunks:
                if b'-----BEGIN CERTIFICATE-----' in chunk:
                    certs.append(x509.load_pem_x509_certificate(chunk + b'-----END CERTIFICATE-----\n'))
        else:
            certs.append(x509.load_der_x509_certificate(data))
    return certs


def _validar_assinatura(cert: x509.Certificate, payload: bytes, signature_base64: str) -> None:
    try:
        signature = base64.b64decode(signature_base64)
    except Exception as exc:
        raise CertificateAuthError('Assinatura em base64 invalida') from exc

    public_key = cert.public_key()
    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(signature, payload, padding.PKCS1v15(), hashes.SHA256())
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
        else:
            raise CertificateAuthError('Tipo de chave do certificado nao suportado')
    except InvalidSignature as exc:
        raise CertificateAuthError('Assinatura do desafio invalida') from exc


def _extrair_identidade(cert: x509.Certificate) -> CertificateIdentity:
    subject = cert.subject.rfc4514_string()
    issuer = cert.issuer.rfc4514_string()
    common_name = _first_name_attr(cert, NameOID.COMMON_NAME)
    email = _first_name_attr(cert, NameOID.EMAIL_ADDRESS) or _email_from_san(cert)
    cpf = _extract_digits(subject, 11)
    cnpj = _extract_digits(subject, 14)
    return CertificateIdentity(
        subject=subject,
        issuer=issuer,
        serial_number=format(cert.serial_number, 'x'),
        common_name=common_name,
        email=email,
        cpf=cpf,
        cnpj=cnpj,
    )


def _first_name_attr(cert: x509.Certificate, oid: x509.ObjectIdentifier) -> str:
    values = cert.subject.get_attributes_for_oid(oid)
    return values[0].value if values else ''


def _email_from_san(cert: x509.Certificate) -> str:
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        emails = san.get_values_for_type(x509.RFC822Name)
        return emails[0] if emails else ''
    except x509.ExtensionNotFound:
        return ''


def _extract_digits(text: str, size: int) -> str:
    for candidate in re.findall(r'\d{%d}' % size, text):
        return candidate
    return ''
