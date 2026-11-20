"""Unit tests for the cryptographic core."""

import tempfile
import os
import unittest

from applocker.core.crypto import PasswordHasher, LocalKeyStore


class PasswordHasherTest(unittest.TestCase):
    def setUp(self):
        self.hasher = PasswordHasher()

    def test_hash_roundtrip(self):
        stored = self.hasher.hash("correct horse battery staple")
        self.assertTrue(stored.startswith("scrypt$"))
        self.assertTrue(self.hasher.verify("correct horse battery staple", stored))

    def test_wrong_password_fails(self):
        stored = self.hasher.hash("right-password")
        self.assertFalse(self.hasher.verify("wrong-password", stored))

    def test_salts_are_unique(self):
        a = self.hasher.hash("same")
        b = self.hasher.hash("same")
        self.assertNotEqual(a, b)

    def test_empty_or_garbage_stored(self):
        self.assertFalse(self.hasher.verify("x", ""))
        self.assertFalse(self.hasher.verify("x", "garbage"))
        self.assertFalse(self.hasher.verify("x", None))

    def test_no_plaintext_in_hash(self):
        stored = self.hasher.hash("secret-returned")
        self.assertNotIn("secret", stored)


class LocalKeyStoreTest(unittest.TestCase):
    def test_key_roundtrip(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "key.bin")
        ks = LocalKeyStore(path)
        key = ks.get_key()
        self.assertEqual(len(key), 32)
        # Reload preserves key.
        ks2 = LocalKeyStore(path)
        self.assertEqual(ks2.get_key(), key)
        fernet = ks2.get_fernet()
        token = fernet.encrypt(b"secret")
        self.assertEqual(fernet.decrypt(token), b"secret")


if __name__ == "__main__":
    unittest.main()