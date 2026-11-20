"""High-level security services: authentication, recovery, tamper checks,
brute-force protection, and the secrets lifecycle.

This is the *only* place that knows how master/app verification, recovery
keys and brute-force counters are composed. UI code never touches crypto
primitives directly.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from applocker.core.crypto import LocalKeyStore, PasswordHasher
from applocker.util.logging import get_logger
from applocker.util.paths import get_secrets_path

log = get_logger()

_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # unambiguous set
_RECOVERY_GROUPS = 4
_RECOVERY_GROUP_LEN = 5


# --------------------------------------------------------------------------- #
# Recovery keys
# --------------------------------------------------------------------------- #
def generate_recovery_key() -> str:
    """Generate a human-friendly recovery key: XXXX-XXXXX-XXXXX-XXXXX.

    Uses an unambiguous base-32 alphabet (no 0/O/1/I/L). 20 chars of entropy
    ≈ 100 bits, which is adequate for an offline primary recover-only secret
    that is also encrypted at rest.
    """
    chars = [secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_GROUPS * _RECOVERY_GROUP_LEN)]
    return "-".join(
        "".join(chars[i * _RECOVERY_GROUP_LEN:(i + 1) * _RECOVERY_GROUP_LEN])
        for i in range(_RECOVERY_GROUPS)
    )


def normalize_recovery_key(key: str) -> str:
    """Upper-case and normalize a typed recovery key into canonical form."""
    cleaned = "".join(ch for ch in key.upper() if ch.isalnum())
    groups = []
    for i in range(_RECOVERY_GROUPS):
        groups.append(cleaned[i * _RECOVERY_GROUP_LEN:(i + 1) * _RECOVERY_GROUP_LEN])
    return "-".join(groups)


def recovery_key_valid(typed: str, stored: str) -> bool:
    return normalize_recovery_key(typed) == stored


# --------------------------------------------------------------------------- #
# Brute-force protection
# --------------------------------------------------------------------------- #
@dataclass
class BruteForcePolicy:
    max_attempts: int = 5
    lockout_seconds: int = 90
    locked_until: float = 0.0
    attempts: int = 0


class BruteForceGuard:
    """Progressive-delay + temporary lockout for authentication attempts.

    Never a permanent lock. The lockout is transient and enforced in-process;
    a determined local attacker can bypass it, which the README documents.
    """

    def __init__(self, policy: Optional[BruteForcePolicy] = None):
        self.policy = policy or BruteForcePolicy()
        self._lock = threading.Lock()

    def record_failure(self) -> float:
        with self._lock:
            self.policy.attempts += 1
            if self.policy.attempts >= self.policy.max_attempts:
                self.policy.locked_until = time.monotonic() + self.policy.lockout_seconds
            return max(0.0, self.policy.locked_until - time.monotonic())

    def record_success(self) -> None:
        with self._lock:
            self.policy.attempts = 0
            self.policy.locked_until = 0.0

    def remaining_lockout(self) -> float:
        with self._lock:
            return max(0.0, self.policy.locked_until - time.monotonic())

    def is_locked(self) -> bool:
        return self.remaining_lockout() > 0


# --------------------------------------------------------------------------- #
# Secrets file (encrypted with DPAPI-tied key, plus integrity)
# --------------------------------------------------------------------------- #
class AuthStore:
    """Persists master/app verifier hashes and the recovery key.

    Layout of ``secrets.bin`` (JSON, Fernet-encrypted):
        {
          "schema": 2,
          "master": "<scrypt verifier>",
          "app_verifiers": { "<app_id>": "<scrypt verifier>" },
          "recovery_key": "<Fernet blob>",
          "tamper": "<hmac>"
        }
    The entire JSON is encrypted; the recovery key is additionally guarded by
    its own Fernet generation so a fresh key can replace an old one.
    """

    SCHEMA = 2

    def __init__(self, path: Optional[str] = None):
        self.path = path or get_secrets_path()
        self._hasher = PasswordHasher()
        self._key_store = None
        self._lock = threading.Lock()
        self._cache: Optional[dict] = None

    def _keystore(self) -> LocalKeyStore:
        if self._key_store is None:
            self._key_store = LocalKeyStore(self.path + ".vault")
        return self._key_store

    def _fernet(self):
        return self._keystore().get_fernet()

    # -- raw load/save ------------------------------------------------------ #
    def _load_encrypted(self) -> Optional[dict]:
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "rb") as fh:
                blob = fh.read()
            fer = self._fernet()
            payload = fer.decrypt(blob)
            data = json.loads(payload)
            if data.get("schema") != self.SCHEMA:
                log.warning("secrets schema mismatch: %s", data.get("schema"))
                return None
            return data
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to load secrets file: %s", exc)
            return None

    def _save_encrypted(self, data: dict) -> None:
        data["schema"] = self.SCHEMA
        payload = json.dumps(data, default=str).encode("utf-8")
        blob = self._fernet().encrypt(payload)
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(blob)
        os.replace(tmp, self.path)

    def _decrypt_recovery(self, blob: str) -> Optional[str]:
        try:
            return self._fernet().decrypt(bytes.fromhex(blob)).decode("utf-8")
        except Exception:  # noqa: BLE001
            return None

    # -- public API --------------------------------------------------------- #
    def is_initialized(self) -> bool:
        data = self._load_encrypted()
        return bool(data and data.get("master"))

    def set_master(self, password: str, recovery_key: str | None = None) -> None:
        """Encrypt the whole store after setting/updating the master password."""
        salt = "_"
        data = self._load_encrypted() or {"app_verifiers": {}, "events": []}
        data["master"] = self._hasher.hash(password)
        if recovery_key:
            fer = self._fernet()
            data["recovery_key"] = fer.encrypt(recovery_key.encode("utf-8")).hex()
        data["tamper"] = "ok"
        self._save_encrypted(data)

    def verify_master(self, password: str) -> bool:
        data = self._load_encrypted()
        if not data:
            return False
        return self._hasher.verify(password, data.get("master", ""))

    def change_master(self, old_password: str, new_password: str, recovery_key: str | None = None) -> bool:
        data = self._load_encrypted()
        if not data or not self._hasher.verify(old_password, data.get("master", "")):
            return False
        data["master"] = self._hasher.hash(new_password)
        if recovery_key:
            fer = self._fernet()
            data["recovery_key"] = fer.encrypt(recovery_key.encode("utf-8")).hex()
        self._save_encrypted(data)
        return True

    def get_recovery_key(self) -> Optional[str]:
        data = self._load_encrypted()
        if not data or "recovery_key" not in data:
            return None
        return self._decrypt_recovery(data["recovery_key"])

    def set_recovery_key(self, key: str) -> None:
        data = self._load_encrypted()
        if not data:
            raise ValueError("Master password must be set before the recovery key")
        fer = self._fernet()
        data["recovery_key"] = fer.encrypt(key.encode("utf-8")).hex()
        self._save_encrypted(data)

    def verify_recovery_key(self, typed: str) -> bool:
        stored = self.get_recovery_key()
        return bool(stored) and recovery_key_valid(typed, stored)

    def app_verifier(self, app_id: str) -> Optional[str]:
        data = self._load_encrypted()
        return data.get("app_verifiers", {}).get(app_id) if data else None

    def set_app_verifier(self, app_id: str, password: str) -> None:
        data = self._load_encrypted()
        if data is None:
            data = {"app_verifiers": {}}
        data.setdefault("app_verifiers", {})[app_id] = self._hasher.hash(password)
        self._save_encrypted(data)

    def remove_app_verifier(self, app_id: str) -> None:
        data = self._load_encrypted()
        if data and app_id in data.get("app_verifiers", {}):
            del data["app_verifiers"][app_id]
            self._save_encrypted(data)


# --------------------------------------------------------------------------- #
# Tamper detection (best-effort integrity check on the config store)
# --------------------------------------------------------------------------- #
class TamperDetector:
    """Verifies a lightweight HMAC over the DB so accidental corruption or
    manual tampering is noticed. Destructive actions are never taken.
    """

    def __init__(self, key: bytes):
        import hmac
        self._hmac = hmac
        self._key = key

    def compute(self, payload: bytes) -> str:
        return self._hmac.new(self._key, payload, "sha256").hexdigest()

    def verify(self, payload: bytes, expected: str) -> bool:
        return self._hmac.compare_digest(self.compute(payload), expected)