# PQC Vault — local Python web application

Run with Python 3.11+ and an ML-KEM-capable cryptography wheel:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8765 in a browser. Stop with Ctrl+C.

1. Create a key pair using a strong, unique private-key password. Download both PEM files and back them up securely.
2. Share only the public key. Verify its SHA-256 fingerprint through an authenticated channel.
3. Upload the recipient public key and a file (maximum 10 MiB); download the `.pqc` envelope.
4. To decrypt, upload the envelope and matching protected private key, supply its password, then download the restored file.

The Python backend uses ML-KEM-768, HKDF-SHA256 and AES-256-GCM. Envelopes include a version marker, encapsulated secret, nonce and authenticated ciphertext. The header is authenticated as associated data. Filenames are not stored in the encrypted envelope. Private keys use password-encrypted PKCS8 PEM serialization. Losing the key or password prevents recovery.

This is an educational, single-user, loopback-only prototype. It does not implement user accounts, sender authentication, replay prevention, certificate trust or a reviewed interoperable protocol. Do not expose it directly to a network. Hosted deployment requires a Python-compatible host, HTTPS, authentication, authorization, rate limits and security review. ML-KEM standardization does not make this application a validated cryptographic module.

Files, keys and passwords reach the Python server in plaintext during processing over local HTTP. No application file storage or request-body logging is used; browser downloads are saved by the user. Python and browser memory are not securely wiped, and browser downloads, OS paging and crash dumps may retain data. Switching tools clears output download links and password fields; selected uploads remain until cleared or the page is closed. This app is separate from the existing petty-cash project and desktop PrivacyShield utility. Their encrypted formats are not compatible.

Verification: `python -m unittest -v test_crypto.py`

Sources:
- NIST FIPS 203: https://csrc.nist.gov/pubs/fips/203/final
- ML-KEM API: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/mlkem/
- AES-GCM: https://cryptography.io/en/latest/hazmat/primitives/aead/
