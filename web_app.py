"""Loopback-only web application. Run: python app.py"""
import base64
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.exceptions import InvalidTag, UnsupportedAlgorithm
from crypto_core import decrypt, encrypt, fingerprint, generate_keys

HOST, PORT = '127.0.0.1', 8765
ORIGIN = f'http://{HOST}:{PORT}'
TOKEN = secrets.token_urlsafe(32)
MAX_REQUEST = 15 * 1024 * 1024


def encode(data):
    return base64.b64encode(data).decode('ascii')


def decode(value):
    if not isinstance(value, str):
        raise ValueError('Invalid file encoding.')
    return base64.b64decode(value, validate=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # Do not log request bodies, passwords or file contents.

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def reply(self, status, data, content_type='application/json'):
        body = json.dumps(data).encode() if content_type == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy',
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') == f'{HOST}:{PORT}'

    def do_GET(self):
        if not self.valid_host():
            return self.reply(403, {'error': 'Invalid host.'})
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path == '/session':
            return self.reply(200, {'token': TOKEN})
        if self.path not in assets:
            return self.reply(404, {'error': 'Not found.'})
        name, mime = assets[self.path]
        self.reply(200, Path(__file__).with_name(name).read_bytes(), mime)

    def do_POST(self):
        if (not self.valid_host() or self.headers.get('Origin') != ORIGIN
                or not secrets.compare_digest(self.headers.get('X-PQC-Token', ''), TOKEN)):
            return self.reply(403, {'error': 'Refresh the page and try again.'})
        try:
            if self.headers.get('Content-Type') != 'application/json':
                raise ValueError('JSON request required.')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_REQUEST:
                return self.reply(413, {'error': 'Request exceeds the file limit.'})
            args = json.loads(self.rfile.read(size))
            if not isinstance(args, dict):
                raise ValueError('Invalid request.')
            if self.path == '/api/keys':
                public, private = generate_keys(args['password'])
                result = {'public': encode(public), 'private': encode(private),
                          'fingerprint': fingerprint(public)}
            elif self.path == '/api/encrypt':
                public = decode(args['key'])
                result = {'file': encode(encrypt(decode(args['file']), public)),
                          'fingerprint': fingerprint(public)}
            elif self.path == '/api/decrypt':
                result = {'file': encode(decrypt(decode(args['file']),
                    decode(args['key']), args['password']))}
            else:
                return self.reply(404, {'error': 'Not found.'})
            self.reply(200, result)
        except (InvalidTag, ValueError, TypeError, KeyError):
            self.reply(400, {'error': 'Unable to process: check file, key and password. '
                'The file may be damaged or the key may be incompatible.'})
        except UnsupportedAlgorithm:
            self.reply(400, {'error': 'This cryptography backend does not support ML-KEM.'})
        except Exception:
            self.reply(500, {'error': 'Processing failed. No output was created.'})


if __name__ == '__main__':
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f'PQC Vault is running at {ORIGIN}', flush=True)
    print('Local prototype. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
