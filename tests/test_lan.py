"""Verify actual LAN TLS, pairing and the public bootstrap boundary."""
import ipaddress
import json
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from bmo.app import Engine, create_server, parse_args
from bmo.lan import create_setup_server, prepare_certificates
try:
    from cryptography import x509
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@unittest.skipUnless(HAS_CRYPTO, 'Optional LAN tests require cryptography')
class LANTests(unittest.TestCase):
    def test_auto_connection_keeps_tls_and_request_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            cert, key, _, _ = prepare_certificates('192.168.137.1', folder)
            args = parse_args(['--tls-cert', str(cert), '--tls-key', str(key), '--auto-connect'])
            args.port = 0
            engine = Engine(args)
            server = create_server(engine)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            url = f'https://127.0.0.1:{server.server_port}'
            context = ssl.create_default_context(cafile=str(Path(folder) / 'rootCA.pem'))
            def get(path, headers=None):
                return urllib.request.urlopen(urllib.request.Request(url + path, headers=headers or {}), context=context)
            def post(path, payload, headers=None):
                return urllib.request.urlopen(urllib.request.Request(url + path, data=json.dumps(payload).encode(),
                    headers={'Content-Type': 'application/json', 'Origin': url, **(headers or {})}), context=context)
            def denied(action):
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    action()
                self.assertEqual(failure.exception.code, 403)
            try:
                with get('/api/state?role=phone') as response:
                    token = json.load(response)['token']
                    self.assertIsNone(response.headers.get('Set-Cookie'))
                with post('/api/chat', {'question': '안녕'}, {'X-BMO-Token': token}) as response:
                    self.assertTrue(json.load(response)['mock'])
                denied(lambda: post('/api/chat', {'question': '안녕'}))
                denied(lambda: post('/api/chat', {'question': '안녕'}, {'X-BMO-Token': 'old-token'}))
                denied(lambda: post('/api/chat', {'question': '안녕'}, {'X-BMO-Token': token, 'Origin': 'https://other.example'}))
                denied(lambda: get('/api/state', {'Host': 'other.example'}))
                denied(lambda: get('/api/state', {'Origin': 'https://other.example'}))
                with patch.object(server.RequestHandlerClass, 'admin_local', return_value=False):
                    with get('/api/state?role=phone') as response:
                        self.assertEqual(response.status, 200)
                    denied(lambda: get('/admin'))
                    denied(lambda: get('/api/state?role=pc'))
                    denied(lambda: post('/api/admin/scene', {'mode': 'off'}, {'X-BMO-Token': token}))
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                engine.close()

    def test_auto_connection_setup_does_not_request_a_code(self):
        server = create_setup_server('192.168.137.1', 0, 'https://192.168.137.1:8768/phone',
                                    b'public-cert', 'fingerprint', bind='127.0.0.1', require_pairing=False)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/') as response:
                page = response.read().decode()
            self.assertIn('연결 코드 없이 자동으로 연결됩니다.', page)
            self.assertNotIn('연결 코드</b>를 입력', page)
            self.assertNotIn('연결 코드는 서버를 다시 시작', page)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_ca_reuse_address_change_and_real_tls_pairing(self):
        with tempfile.TemporaryDirectory() as folder:
            cert, key, ca_der, fingerprint = prepare_certificates('192.168.137.1', folder)
            old_leaf = cert.read_bytes()
            prepare_certificates('192.168.137.1', folder)
            self.assertEqual(old_leaf, cert.read_bytes())
            _, _, updated_ca, updated_fingerprint = prepare_certificates('172.16.71.23', folder)
            self.assertEqual((ca_der, fingerprint), (updated_ca, updated_fingerprint))
            leaf = x509.load_pem_x509_certificate(cert.read_bytes())
            self.assertIn(ipaddress.ip_address('172.16.71.23'), leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress))
            args = parse_args(['--tls-cert', str(cert), '--tls-key', str(key)])
            args.port = 0
            engine = Engine(args)
            server = create_server(engine)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            url = f'https://127.0.0.1:{server.server_port}'
            context = ssl.create_default_context(cafile=str(Path(folder) / 'rootCA.pem'))
            try:
                with self.assertRaises(urllib.error.HTTPError) as unauthorized:
                    urllib.request.urlopen(url + '/api/state', context=context)
                self.assertEqual(unauthorized.exception.code, 401)
                request = urllib.request.Request(url + '/api/pair', data=json.dumps({'code': engine.pair_code}).encode(), headers={'Origin': url})
                with urllib.request.urlopen(request, context=context) as response:
                    cookie = response.headers['Set-Cookie'].split(';')[0]
                    self.assertIn('Secure', response.headers['Set-Cookie'])
                request = urllib.request.Request(url + '/api/state', headers={'Cookie': cookie})
                with urllib.request.urlopen(request, context=context) as response:
                    self.assertEqual(json.load(response)['provider'], 'mock')
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                engine.close()

    def test_setup_serves_only_public_certificate_and_no_api(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, ca_der, fingerprint = prepare_certificates('192.168.137.1', folder)
            server = create_setup_server('192.168.137.1', 0, 'https://192.168.137.1:8766/phone', ca_der, fingerprint, bind='127.0.0.1')
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            url = f'http://127.0.0.1:{server.server_port}'
            try:
                with urllib.request.urlopen(url + '/') as response:
                    self.assertIn('https://192.168.137.1:8766/phone', response.read().decode())
                with urllib.request.urlopen(url + '/rootCA.cer') as response:
                    self.assertEqual(response.read(), ca_der)
                    self.assertEqual(response.headers.get_content_type(), 'application/x-x509-ca-cert')
                for path in ('/rootCA-key.pem', '/bmo-key.pem', '/api/state', '/../bmo/private_config.py'):
                    with self.assertRaises(urllib.error.HTTPError) as forbidden:
                        urllib.request.urlopen(url + path)
                    self.assertEqual(forbidden.exception.code, 404)
                with self.assertRaises(urllib.error.HTTPError) as bad_host:
                    urllib.request.urlopen(urllib.request.Request(url, headers={'Host': 'untrusted.example'}))
                self.assertEqual(bad_host.exception.code, 403)
                with self.assertRaises(urllib.error.HTTPError) as post:
                    urllib.request.urlopen(urllib.request.Request(url + '/api/pair', data=b'{}'))
                self.assertEqual(post.exception.code, 405)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
