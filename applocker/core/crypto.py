"""Cryptographic core for AppLocker.

Goal: no plaintext passwords, no custom crypto, no secrets in logs.

Authentication hashes
    Master and application passwords are stored as *verifier hashes* derived
    with ``scrypt`` (memory-hard, salted, per-password random salt). This lets
    the app *verify* a password offline without ever being able to reverse it
    and without storing the password itself.

Encrypted secrets
    Reversible secrets (e.g. the recovery key) are encrypted with ``Fernet``
    (AES-128-CBC + HMAC) using a key that is DPAPI-protected on this user's
    profile. This keeps secrets out of plaintext while tying them to the
    current logged-in user.

Windows DPAPI
    ``CryptProtectData`` / ``CryptUnprotectData`` ties stored bytes to the
    current logged-in user and machine. Used as a storage protection layer,
    not the only secret.

We deliberately do not roll our own cryptography.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from applocker.util.logging import get_logger

log = get_logger()

# scrypt parameters (memory-hard; ~64 MB of memory as recommended for passwords).
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_LEN = 32
_HASH_PREFIX = "scrypt$v1$"

# Domain-separation for the verifier hash vs the encryption key.
_VERIFIER_SALT_TAG = b"applocker:verifier"

_DPAPI_APP_DESC = "AppLocker secrets v1"
_DPAPI_KEY_MARKER = b"APPLOCKER_KEY1:"


def _crypt_protect(data: bytes) -> bytes:
    """DPAPI-protect bytes tied to the current user."""

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf_in = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf_in, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        ctypes.c_wchar_p(_DPAPI_APP_DESC),
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _crypt_unprotect(data: bytes) -> bytes:
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptUnprotectData failed — wrong user or machine context")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _derive_verifier(password: str, salt: bytes, *, rounds: int | None = None) -> bytes:
    n = rounds if rounds is not None else _SCRYPT_N
    kdf = Scrypt(salt=salt + _VERIFIER_SALT_TAG, length=_SCRYPT_LEN, n=n, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


# --------------------------------------------------------------------------- #
# Verifier hashes (authentication)
# --------------------------------------------------------------------------- #
class PasswordHasher:
    """Creates and verifies salted scrypt verifier hashes.

    Stored form: ``scrypt$v1$<n>$<salt_b64>$<hash_b64>``
    """

    def __init__(self, n: int = _SCRYPT_N):
        self.n = n

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = _derive_verifier(password, salt, rounds=self.n)
        return "{}{}${}${}".format(
            _HASH_PREFIX,
            self.n,
            base64.urlsafe_b64encode(salt).decode(),
            base64.urlsafe_b64encode(digest).decode(),
        )

    def verify(self, password: str, stored: str) -> bool:
        if not stored or not stored.startswith(_HASH_PREFIX):
            return False
        try:
            _, _, n_s, salt_b64, digest_b64 = stored.split("$")
            salt = base64.urlsafe_b64decode(salt_b64)
            expected = base64.urlsafe_b64decode(digest_b64)
        except (ValueError, TypeError):
            return False
        try:
            actual = _derive_verifier(password, salt, rounds=int(n_s))
        except Exception:  # noqa: BLE001
            return False
        return hmac.compare_digest(actual, expected)


# --------------------------------------------------------------------------- #
# DPAPI-protected local key cache (for encrypted secrets)
# --------------------------------------------------------------------------- #
class LocalKeyStore:
    """Generates and persists a single 32-byte Fernet key via DPAPI.

    The key is created once and stored DPAPI-protected in a file in the app
    data directory. It is used to encrypt reversible secrets (recovery key).
    """

    KEY_LEN = 32

    def __init__(self, path: str):
        self.path = path
        self._key: bytes | None = None

    def _load(self) -> bytes | None:
        try:
            with open(self.path, "rb") as fh:
                raw = fh.read()
            if not raw.startswith(_DPAPI_KEY_MARKER):
                return None
            return _crypt_unprotect(raw[len(_DPAPI_KEY_MARKER):])
        except OSError:
            return None

    def _save(self, key: bytes) -> None:
        protected = _crypt_protect(key)
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(_DPAPI_KEY_MARKER + protected)
        import os
        os.replace(tmp, self.path)

    def get_key(self) -> bytes:
        if self._key is not None:
            return self._key
        key = self._load()
        if key is None:
            key = secrets.token_bytes(self.KEY_LEN)
            self._save(key)
        self._key = key
        return key

    def get_fernet(self) -> Fernet:
        raw = self.get_key()
        if len(raw) != 32:
            raise ValueError("Stored key has an invalid length")
        return Fernet(base64.urlsafe_b64encode(raw))

    def reset(self) -> None:
        self._key = None
        import os
        try:
            os.remove(self.path)
        except OSError:
            pass


def protect_data(data: bytes, description: str = _DPAPI_APP_DESC) -> bytes:
    return _crypt_protect(data)


def unprotect_data(data: bytes, description: str = _DPAPI_APP_DESC) -> bytes:
    return _crypt_unprotect(data)
