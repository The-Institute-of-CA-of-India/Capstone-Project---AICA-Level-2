"""Versioned educational ML-KEM-768 / AES-256-GCM file envelope."""
import hashlib
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.mlkem import MLKEM768PrivateKey, MLKEM768PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b'PQCWEB01'
MAX_FILE = 10 * 1024 * 1024
HEADER_SIZE = len(MAGIC) + 1088 + 12


def fingerprint(public_pem):
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, MLKEM768PublicKey):
        raise ValueError('An ML-KEM-768 public key is required.')
    return hashlib.sha256(key.public_bytes_raw()).hexdigest()


def generate_keys(password):
    if len(password) < 12:
        raise ValueError('Use a private-key password of at least 12 characters.')
    key = MLKEM768PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    private = key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(password.encode('utf-8')))
    return public, private


def derive(secret):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=b'pqc-web/ml-kem-768/aes-256-gcm/v1').derive(secret)


def encrypt(data, public_pem):
    if len(data) > MAX_FILE:
        raise ValueError('Files must be 10 MiB or smaller.')
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, MLKEM768PublicKey):
        raise ValueError('An ML-KEM-768 public key is required.')
    secret, encapsulated = key.encapsulate()
    nonce = os.urandom(12)
    header = MAGIC + encapsulated + nonce
    return header + AESGCM(derive(secret)).encrypt(nonce, data, header)


def decrypt(envelope, private_pem, password):
    if not HEADER_SIZE + 16 <= len(envelope) <= HEADER_SIZE + 16 + MAX_FILE:
        raise ValueError('Invalid encrypted file size.')
    if not envelope.startswith(MAGIC):
        raise ValueError('Unsupported file format. Select a .pqc file from this app.')
    key = serialization.load_pem_private_key(private_pem, password.encode('utf-8'))
    if not isinstance(key, MLKEM768PrivateKey):
        raise ValueError('An ML-KEM-768 private key is required.')
    header = envelope[:HEADER_SIZE]
    secret = key.decapsulate(header[len(MAGIC):-12])
    return AESGCM(derive(secret)).decrypt(header[-12:], envelope[HEADER_SIZE:], header)
