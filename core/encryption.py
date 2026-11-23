"""Field-level encryption helpers (Fernet = AES-128-CBC + HMAC-SHA256, authenticated).

Keys live in environment variables, never in the code or the database:
  FIELD_ENCRYPTION_KEYS  comma-separated Fernet keys, NEWEST FIRST (older ones kept so old rows can still be read)
  FIELD_INDEX_KEY        a separate secret used only for searchable 'blind indexes'
"""
import hashlib
import hmac

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _cipher():
    keys = getattr(settings, "FIELD_ENCRYPTION_KEYS", [])
    if not keys:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS is not set. Generate one with: "
                                   "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
    return MultiFernet([Fernet(k) for k in keys])      # encrypts with the first key, decrypts with any


def encrypt(text: str) -> str:
    return _cipher().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    return _cipher().decrypt(token.encode("ascii")).decode("utf-8")


def blind_index(value: str) -> str:
    """Deterministic keyed hash for EXACT-MATCH search on an encrypted value (case/space-insensitive)."""
    secret = getattr(settings, "FIELD_INDEX_KEY", "")
    if not secret:
        raise ImproperlyConfigured("FIELD_INDEX_KEY is not set.")
    normal = " ".join(value.lower().split())
    return hmac.new(secret.encode(), normal.encode(), hashlib.sha256).hexdigest()
