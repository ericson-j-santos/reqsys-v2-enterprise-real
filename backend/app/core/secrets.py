from __future__ import annotations

import logging
import os
import secrets as _secrets
from base64 import b64decode, b64encode

_logger = logging.getLogger(__name__)

try:
    import keyring  # type: ignore
    _KEYRING_OK = True
except ImportError:
    keyring = None
    _KEYRING_OK = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    requests = None  # type: ignore
    _REQUESTS_OK = False


_DEFAULT_VAULT_SERVICE = 'mvp-intelligence-vault'
_MASTER_KEY_SLOT = '__master_key__'
_NONCE_BYTES = 12


def _vault_service_name() -> str:
    return os.getenv('REQSYS_VAULT_SERVICE_NAME', _DEFAULT_VAULT_SERVICE).strip() or _DEFAULT_VAULT_SERVICE


def init_vault(service_name: str | None = None, overwrite: bool = False) -> bool:
    """Cria master key no keyring. Retorna True se criada, False se já existia."""
    if not (_KEYRING_OK and _CRYPTO_OK):
        return False
    service = service_name or _vault_service_name()
    existing = keyring.get_password(service, _MASTER_KEY_SLOT)
    if existing and not overwrite:
        return False
    master_key = _secrets.token_bytes(32)
    keyring.set_password(service, _MASTER_KEY_SLOT, b64encode(master_key).decode())
    return True


def read_secret_from_vault(key: str, service_name: str | None = None) -> str | None:
    if not key or not (_KEYRING_OK and _CRYPTO_OK):
        return None

    service = service_name or _vault_service_name()
    try:
        raw_master_key = keyring.get_password(service, _MASTER_KEY_SLOT)
        if not raw_master_key:
            return None

        blob = keyring.get_password(service, key)
        if blob is None:
            return None

        master_key = b64decode(raw_master_key)
        raw = b64decode(blob)
        nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return AESGCM(master_key).decrypt(nonce, ciphertext, None).decode()
    except Exception:
        _logger.warning('Falha ao descriptografar segredo "%s" no vault "%s"', key, service)
        return None


def write_secret_to_vault(key: str, value: str, service_name: str | None = None) -> None:
    """Criptografa e grava segredo no keyring."""
    if not key or not key.strip():
        raise ValueError('Chave não pode ser vazia')
    if not (_KEYRING_OK and _CRYPTO_OK):
        raise RuntimeError('Vault não disponível: keyring ou cryptography não instalados')
    service = service_name or _vault_service_name()
    raw_master_key = keyring.get_password(service, _MASTER_KEY_SLOT)
    if not raw_master_key:
        raise RuntimeError('Vault não inicializado. Chame init_vault() ou POST /v1/cofre/init primeiro')
    master_key = b64decode(raw_master_key)
    nonce = _secrets.token_bytes(_NONCE_BYTES)
    ciphertext = AESGCM(master_key).encrypt(nonce, value.encode(), None)
    blob = b64encode(nonce + ciphertext).decode()
    keyring.set_password(service, key, blob)


def delete_secret_from_vault(key: str, service_name: str | None = None) -> bool:
    """Remove segredo do keyring. Retorna True se existia."""
    if not _KEYRING_OK:
        return False
    service = service_name or _vault_service_name()
    try:
        existing = keyring.get_password(service, key)
        if existing is None:
            return False
        keyring.delete_password(service, key)
        return True
    except Exception:
        return False


def vault_initialized(service_name: str | None = None) -> bool:
    if not _KEYRING_OK:
        return False
    service = service_name or _vault_service_name()
    try:
        return bool(keyring.get_password(service, _MASTER_KEY_SLOT))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# vault-service remoto (extração do cofre, ADR-041) — fallback opcional além do
# keyring local. Lido direto de os.environ (nao de app.core.config.settings) de
# proposito: Settings() e construido chamando get_secret() para cada campo, entao
# depender de `settings` aqui criaria um ciclo de bootstrap.
# ---------------------------------------------------------------------------

_REMOTE_CIRCUIT_FAILURE_THRESHOLD = 3
_REMOTE_CIRCUIT_COOLDOWN_SECONDS = 60
_remote_circuit = None  # type: ignore[var-annotated]


def _cofre_service_base_url() -> str:
    return os.getenv('COFRE_API_URL', '').strip()


def _cofre_service_token() -> str:
    return os.getenv('COFRE_SERVICE_TOKEN', '').strip()


def _cofre_service_timeout_seconds() -> float:
    try:
        return float(os.getenv('COFRE_SERVICE_TIMEOUT_SECONDS', '5') or '5')
    except ValueError:
        return 5.0


def _remote_vault_circuit():
    global _remote_circuit
    if _remote_circuit is None:
        from app.core.resilience import CircuitBreaker
        _remote_circuit = CircuitBreaker(
            name='cofre_service_remoto',
            failure_threshold=_REMOTE_CIRCUIT_FAILURE_THRESHOLD,
            cooldown_seconds=_REMOTE_CIRCUIT_COOLDOWN_SECONDS,
        )
    return _remote_circuit


def read_secret_from_remote_vault(key: str) -> str | None:
    """Le um segredo do vault-service remoto (timeout + retry + circuit breaker, ADR-010).

    Retorna None (nunca levanta) sempre que o serviço remoto nao estiver configurado,
    indisponivel ou com o circuito aberto — quem chama trata isso como "nao resolvido
    por aqui" e segue para o proximo fallback (mesmo contrato de read_secret_from_vault).
    """
    if not key or not _REQUESTS_OK:
        return None
    base_url = _cofre_service_base_url()
    token = _cofre_service_token()
    if not base_url or not token:
        return None

    from app.core.resilience import CircuitBreakerOpenError, call_with_retry

    url = f"{base_url.rstrip('/')}/v1/segredos/{key}"

    def _do_get() -> str | None:
        resposta = requests.get(
            url, headers={'X-Vault-Token': token}, timeout=_cofre_service_timeout_seconds()
        )  # nosec B113 - timeout sempre presente (default 5s via _cofre_service_timeout_seconds)
        if resposta.status_code == 404:
            return None
        resposta.raise_for_status()
        return resposta.json().get('value')

    try:
        return call_with_retry(
            _do_get,
            max_retries=2,
            backoff_seconds=0.3,
            retry_on=(requests.ConnectionError, requests.Timeout),
            circuit=_remote_vault_circuit(),
        )
    except CircuitBreakerOpenError:
        _logger.warning('Circuito do vault-service remoto aberto; usando fallback local/default para "%s"', key)
        return None
    except Exception:
        _logger.warning('Falha ao ler segredo "%s" do vault-service remoto', key)
        return None


def get_secret(
    name: str,
    default: str | None = None,
    *,
    env_name: str | None = None,
    vault_key: str | None = None,
    prefer_vault: bool = False,
) -> str | None:
    env_key = env_name or name
    secret_key = vault_key or name
    env_value = os.getenv(env_key)

    if prefer_vault:
        vault_value = read_secret_from_vault(secret_key)
        if vault_value not in (None, ''):
            return vault_value
        if env_value not in (None, ''):
            return env_value
        remote_value = read_secret_from_remote_vault(secret_key)
        if remote_value not in (None, ''):
            return remote_value
        return default

    if env_value not in (None, ''):
        return env_value

    vault_value = read_secret_from_vault(secret_key)
    if vault_value not in (None, ''):
        return vault_value

    remote_value = read_secret_from_remote_vault(secret_key)
    if remote_value not in (None, ''):
        return remote_value

    return default


def describe_secret_resolution(
    name: str,
    default: str | None = None,
    *,
    env_name: str | None = None,
    vault_key: str | None = None,
    prefer_vault: bool = False,
) -> dict[str, object]:
    env_key = env_name or name
    secret_key = vault_key or name
    env_value = os.getenv(env_key)
    vault_value = read_secret_from_vault(secret_key)

    has_vault = vault_value not in (None, '')
    has_env = env_value not in (None, '')
    # Só consulta o vault-service remoto se nem env nem vault local resolverem —
    # evita uma chamada de rede por segredo monitorado na tela de diagnóstico.
    has_remote = False
    if not has_env and not has_vault:
        has_remote = read_secret_from_remote_vault(secret_key) not in (None, '')

    if prefer_vault and has_vault:
        source = 'vault'
    elif has_env:
        source = 'env'
    elif has_vault:
        source = 'vault'
    elif has_remote:
        source = 'vault_remoto'
    elif default is not None:
        source = 'default'
    else:
        source = 'absent'

    configured = source != 'absent'

    return {
        'name': name,
        'env_name': env_key,
        'vault_key': secret_key,
        'source': source,
        'configured': configured,
        'resolved': configured,
        'using_default': source == 'default',
        'prefer_vault': prefer_vault,
        'vault_service_name': _vault_service_name(),
        'value_exposed': False,
    }
