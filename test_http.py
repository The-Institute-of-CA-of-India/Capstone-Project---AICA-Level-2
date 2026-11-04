"""Integration check against a running local app.py server."""
import base64
import json
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8765'
with urllib.request.urlopen(BASE, timeout=10) as response:
    assert response.status == 200
    assert b'PQC VAULT' in response.read()
with urllib.request.urlopen(BASE + '/session', timeout=10) as response:
    token = json.load(response)['token']


def post(path, data, authenticated=True):
    headers = {'Content-Type': 'application/json', 'Origin': BASE}
    if authenticated:
        headers['X-PQC-Token'] = token
    request = urllib.request.Request(BASE + '/api/' + path,
        json.dumps(data).encode(), headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


keys = post('keys', {'password': 'integration-test-only'})
plain = base64.b64encode(b'HTTP encryption roundtrip').decode()
encrypted = post('encrypt', {'file': plain, 'key': keys['public']})
decrypted = post('decrypt', {'file': encrypted['file'], 'key': keys['private'],
                           'password': 'integration-test-only'})
assert decrypted['file'] == plain
try:
    post('keys', {'password': 'integration-test-only'}, False)
    raise AssertionError('Missing token accepted')
except urllib.error.HTTPError as error:
    assert error.code == 403
print('HTTP checks passed: page, keys, encryption, decryption, CSRF rejection')
