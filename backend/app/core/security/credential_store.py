"""Encrypted-at-rest credential storage.

v1.0.0 only needs this for the SNMP read community string, but the pattern
is built out fully now so write-credentials (SSH, vendor APIs) added in
later versions don't require retrofitting storage — see IEC 62443-4-1
baseline notes in the project plan.

The encryption key itself never touches disk in plaintext: it is held in
the OS credential store (Windows Credential Manager on the deployment
target) via `keyring`, not in `credentials.enc` alongside the data it
protects.
"""

import json

import keyring
from cryptography.fernet import Fernet

from app.core.paths import DATA_DIR

_SERVICE_NAME = "open-vision-vite"
_KEYRING_KEY_NAME = "credential-store-key"
_STORE_PATH = DATA_DIR / "credentials.enc"

_DEFAULTS = {"snmp_community": "public"}


def _get_or_create_key() -> bytes:
    existing = keyring.get_password(_SERVICE_NAME, _KEYRING_KEY_NAME)
    if existing:
        return existing.encode()

    key = Fernet.generate_key()
    keyring.set_password(_SERVICE_NAME, _KEYRING_KEY_NAME, key.decode())
    return key


def _load_store() -> dict[str, str]:
    if not _STORE_PATH.exists():
        return dict(_DEFAULTS)

    fernet = Fernet(_get_or_create_key())
    encrypted = _STORE_PATH.read_bytes()
    decrypted = fernet.decrypt(encrypted)
    return json.loads(decrypted)


def _save_store(store: dict[str, str]) -> None:
    fernet = Fernet(_get_or_create_key())
    encrypted = fernet.encrypt(json.dumps(store).encode())
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_bytes(encrypted)


def get_credential(key: str) -> str | None:
    store = _load_store()
    return store.get(key, _DEFAULTS.get(key))


def set_credential(key: str, value: str) -> None:
    store = _load_store()
    store[key] = value
    _save_store(store)
