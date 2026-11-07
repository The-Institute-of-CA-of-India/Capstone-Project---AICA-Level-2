"""Entry point.  python run.py [--port N] [--host H] [--debug] [--https]

--https serves over TLS with a self-signed certificate. Browsers only allow
service workers (PWA install, offline mode) on https:// or localhost, so phones
connecting over the LAN need this flag.
"""
import argparse
import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import create_app
from config import Config


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def ensure_self_signed_cert(cert_root, ip):
    """Create (once per LAN IP) a self-signed certificate for this server."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    root = Path(cert_root)
    root.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = root / f"server-{ip}.crt", root / f"server-{ip}.key"
    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "KnowTaxx AP Suite")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.IPAddress(ipaddress.ip_address(ip)),
        ]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    return str(cert_path), str(key_path)


def main():
    parser = argparse.ArgumentParser(description="KnowTaxx AP & Expense Intelligence Suite")
    parser.add_argument("--host", default=Config.HOST)
    parser.add_argument("--port", type=int, default=Config.PORT)
    parser.add_argument("--debug", action="store_true", help="Flask debug mode (local development only)")
    parser.add_argument("--https", action="store_true", help="serve over TLS with a self-signed certificate")
    args = parser.parse_args()

    app = create_app()
    ip = lan_ip()
    scheme = "https" if args.https else "http"
    print(f"\n  KnowTaxx AP Suite v{Config.VERSION}")
    print(f"  Local:   {scheme}://localhost:{args.port}")
    print(f"  LAN:     {scheme}://{ip}:{args.port}\n")

    if args.https:
        app.config["SESSION_COOKIE_SECURE"] = True
        cert = ensure_self_signed_cert(app.config["CERT_ROOT"], ip)
        app.run(host=args.host, port=args.port, ssl_context=cert, threaded=True, use_reloader=False)
    elif args.debug:
        app.run(host="127.0.0.1", port=args.port, debug=True, use_reloader=False)
    else:
        from waitress import serve
        serve(app, host=args.host, port=args.port, threads=8)


if __name__ == "__main__":
    main()
