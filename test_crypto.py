import unittest
from cryptography.exceptions import InvalidTag
from crypto_core import decrypt, encrypt, generate_keys


class CryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'test-only-strong-password'
        cls.public, cls.private = generate_keys(cls.password)

    def test_roundtrip_binary_and_empty(self):
        for data in (b'', bytes(range(256)) * 8):
            with self.subTest(size=len(data)):
                self.assertEqual(decrypt(encrypt(data, self.public), self.private, self.password), data)

    def test_modified_ciphertext_rejected(self):
        data = bytearray(encrypt(b'confidential', self.public))
        data[-1] ^= 1
        with self.assertRaises(InvalidTag):
            decrypt(bytes(data), self.private, self.password)

    def test_modified_encapsulation_rejected(self):
        data = bytearray(encrypt(b'confidential', self.public))
        data[20] ^= 1
        with self.assertRaises(InvalidTag):
            decrypt(bytes(data), self.private, self.password)

    def test_wrong_password_rejected(self):
        with self.assertRaises(ValueError):
            decrypt(encrypt(b'test', self.public), self.private, 'incorrect')

    def test_wrong_key_rejected(self):
        _, other = generate_keys(self.password)
        with self.assertRaises(InvalidTag):
            decrypt(encrypt(b'test', self.public), other, self.password)

    def test_bad_format_rejected(self):
        with self.assertRaises(ValueError):
            decrypt(b'not-an-envelope', self.private, self.password)

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            generate_keys('short')


if __name__ == '__main__':
    unittest.main()
