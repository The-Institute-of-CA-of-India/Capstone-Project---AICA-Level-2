# PQC Vault — Windows desktop application

## Open the application

Double-click `Launch PQC Vault.cmd`, or open `dist\PQCVaultDesktop\PQCVault.exe`. Keep the entire `PQCVaultDesktop` directory together; the executable depends on its `_internal` subfolder. No separate Python installation is needed for this Windows package. The older `dist\PQCVault` directory, if present, is an earlier preview build; use the launcher for the current version.

Alternatively, run from source with Python 3.11+ (including Tkinter) and an ML-KEM-capable cryptography installation:

```powershell
python -m pip install -r requirements.txt
python app.py
```

## Workflow

1. **Create keys:** enter and confirm a strong private-key password of at least 12 characters. Choose a folder. Both PEM keys are saved with a public-key fingerprint prefix. Back up the protected private key and password securely. Lost keys/passwords cannot be recovered.
2. **Encrypt file:** select the recipient public key and a file up to 10 MiB. Confirm the SHA-256 fingerprint against an authenticated source, then choose a new output filename.
3. **Decrypt file:** select the matching private key, `.pqc` file and password, then choose a new output filename. Modified ciphertext and mismatched keys are rejected.

Existing files are never overwritten. Originals are preserved. Files and keys are processed in memory locally; the desktop app does not start a network server, collect telemetry, or call remote services. Password fields are cleared after an operation starts or the selected tab changes. Python/OS memory is not securely wiped; paging, crash dumps and disk backups may retain sensitive data. The save folder inherits Windows permissions; use a properly protected folder for private keys.

The envelope format is compatible with the earlier PQC Vault web application, using ML-KEM-768, HKDF-SHA256 and AES-256-GCM. The earlier web server is retained as `web_app.py`, with `index.html`, `style.css` and `app.js`. Run it separately with `python web_app.py` only when needed. This format is not compatible with the unrelated PrivacyShield desktop utility.

## Verification and packaging

```powershell
python -m unittest -v test_crypto.py test_desktop.py
python -m PyInstaller --noconfirm --windowed --onedir --name PQCVault app.py
```

Packaging uses PyInstaller, a separate build dependency. The current package is unsigned and Windows may warn about an unrecognised publisher. Source and binaries remain a prototype: obtain an independent security review, appropriate licensing/notices and code signing before commercial distribution. Sender identity and replay prevention are not provided. The application is not a FIPS-validated module.

Sources:
- NIST FIPS 203: https://csrc.nist.gov/pubs/fips/203/final
- ML-KEM API: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/mlkem/
- Cryptography licence: https://github.com/pyca/cryptography/blob/50.0.2/LICENSE
- PyInstaller licensing: https://pyinstaller.org/en/stable/license.html
