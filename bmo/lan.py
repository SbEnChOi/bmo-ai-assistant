"""Private-network HTTPS and a public-certificate-only device setup page."""
import argparse
import datetime
import html
import ipaddress
from pathlib import Path
import ssl
import threading
from http.server import BaseHTTPRequestHandler

from .app import BmoServer, Engine, create_server, parse_args


def prepare_certificates(address, directory):
    ip = ipaddress.ip_address(address)
    if ip.version != 4 or not ip.is_private or ip.is_loopback or ip.is_unspecified or ip.is_link_local:
        raise ValueError("Use this PC's private Wi-Fi IPv4 address.")
    try:
        from cryptography import x509
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    except ImportError as exc:
        raise ValueError('LAN HTTPS requires: python -m pip install -r requirements-lan.txt') from exc
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    ca_path, ca_key_path = directory / 'rootCA.pem', directory / 'rootCA-key.pem'
    now = datetime.datetime.now(datetime.timezone.utc)
    if ca_path.exists() != ca_key_path.exists():
        raise ValueError('Incomplete BMO CA files. Restore the matching certificate and private key.')
    if ca_path.exists():
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        if ca.public_key().public_numbers() != ca_key.public_key().public_numbers():
            raise ValueError('BMO CA certificate and private key do not match.')
        if not ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
            raise ValueError('The saved BMO root is not a CA certificate.')
        if ca.not_valid_after_utc <= now + datetime.timedelta(days=2):
            raise ValueError('BMO CA has expired or is expiring. Create and trust a new CA.')
    else:
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'BMO Local Development CA')])
        ca = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - datetime.timedelta(days=1))
              .not_valid_after(now + datetime.timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, None, None), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
              .sign(ca_key, hashes.SHA256()))
        for path, data in ((ca_key_path, ca_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())),
                           (ca_path, ca.public_bytes(serialization.Encoding.PEM))):
            with path.open('xb') as stream:
                stream.write(data)
            path.chmod(0o600)
    ca_der = ca.public_bytes(serialization.Encoding.DER)
    (directory / 'rootCA.cer').write_bytes(ca_der)
    leaf_path, key_path = directory / 'bmo.pem', directory / 'bmo-key.pem'
    reuse = False
    if leaf_path.exists() and key_path.exists():
        try:
            leaf = x509.load_pem_x509_certificate(leaf_path.read_bytes())
            key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            leaf.verify_directly_issued_by(ca)
            reuse = (leaf.not_valid_after_utc > now + datetime.timedelta(days=14)
                     and leaf.public_key().public_numbers() == key.public_key().public_numbers()
                     and ip in leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress))
        except (ValueError, TypeError, InvalidSignature, x509.ExtensionNotFound):
            pass
    if not reuse:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'BMO local device server')])
        leaf = (x509.CertificateBuilder().subject_name(name).issuer_name(ca.subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(hours=1))
                .not_valid_after(min(now + datetime.timedelta(days=365), ca.not_valid_after_utc))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip), x509.IPAddress(ipaddress.ip_address('127.0.0.1')), x509.DNSName('localhost')]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, None, None), critical=True)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .sign(ca_key, hashes.SHA256()))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        key_path.chmod(0o600)
        leaf_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    return leaf_path, key_path, ca_der, ca.fingerprint(hashes.SHA256()).hex().upper()


def create_setup_server(address, port, device_url, ca_der, fingerprint, bind='0.0.0.0', require_pairing=True):
    connection_step = ('열고 <b>PC에 표시된 연결 코드</b>를 입력합니다.' if require_pairing
                       else '열면 <b>연결 코드 없이 자동으로 연결됩니다.</b>')
    connection_note = ' 연결 코드는 서버를 다시 시작할 때 바뀝니다.' if require_pairing else ''
    access_note = 'HTTPS 연결 및 연결 코드 확인 후' if require_pairing else '같은 네트워크의 HTTPS 주소에서 바로'
    page = f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>BMO 기기 연결</title>
<style>body{{font:17px/1.7 system-ui,sans-serif;background:#d7f0d4;color:#193d38;margin:0}}main{{max-width:620px;margin:40px auto;padding:24px}}h1{{line-height:1.2}}li{{margin:20px 0}}a{{color:#185445}}.button{{display:inline-block;background:#20564b;color:white;padding:10px 18px;border-radius:16px;text-decoration:none}}small{{display:block;overflow-wrap:anywhere}}</style>
<main><h1>BMO와 연결하기</h1><p>아이패드에서는 이 준비 화면을 <b>Safari</b>로 열어 주세요. 인증서 설치 후에는 Chrome에서 BMO를 사용할 수 있습니다.</p>
<ol><li><a class="button" href="/rootCA.cer">BMO 인증서 받기</a><br>다운로드 또는 프로파일 설치를 허용해 주세요.</li>
<li>아이패드 <b>설정 → 일반 → VPN 및 기기 관리</b>에서 <b>BMO Local Development CA</b> 프로파일을 설치합니다.</li>
<li><b>설정 → 일반 → 정보 → 인증서 신뢰 설정</b>에서 <b>BMO Local Development CA</b>의 전체 신뢰를 켭니다.</li>
<li>Chrome에서 아래 주소를 {connection_step} 연결 후 <b>BMO 소리 켜기</b>를 한 번 누릅니다.<br><a class="button" href="{html.escape(device_url, quote=True)}">BMO 화면 열기</a><br><small>{html.escape(device_url)}</small></li></ol>
<p>PC와 아이패드는 같은 Wi-Fi에 연결해 주세요. 인증서는 처음 한 번 설치합니다.{connection_note}</p>
<details><summary>인증서 확인 정보</summary><small>SHA-256: {html.escape(fingerprint)}</small><p>이 준비 페이지는 공개 인증서만 제공합니다. BMO 대화와 음성은 {access_note} 사용할 수 있습니다.</p></details></main></html>'''.encode()

    class SetupHandler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_):
            pass

        def do_GET(self):
            hosts = {f'{address}:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host', '').lower() not in hosts:
                return self.respond(403, b'Forbidden', 'text/plain')
            if self.path == '/':
                return self.respond(200, page, 'text/html; charset=utf-8')
            if self.path == '/rootCA.cer':
                return self.respond(200, ca_der, 'application/x-x509-ca-cert')
            self.respond(404, b'Not found', 'text/plain')

        def do_POST(self):
            self.respond(405, b'Method not allowed', 'text/plain')

        def respond(self, code, data, mime):
            self.send_response(code)
            for key, value in {'Content-Type': mime, 'Content-Length': str(len(data)), 'Cache-Control': 'no-store',
                               'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                               'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    return BmoServer((bind, port), SetupHandler)


def main():
    parser = argparse.ArgumentParser(description='BMO private-network HTTPS setup', add_help=False)
    parser.add_argument('--address', required=True)
    parser.add_argument('--cert-dir', default='certs')
    parser.add_argument('--setup-port', type=int, default=8767)
    parser.add_argument('--prepare-only', action='store_true')
    setup, remaining = parser.parse_known_args()
    engine = server = bootstrap = thread = None
    try:
        cert, key, ca_der, fingerprint = prepare_certificates(setup.address, setup.cert_dir)
        if setup.prepare_only:
            print(f'Public certificate: {Path(setup.cert_dir).resolve() / "rootCA.cer"}')
            print(f'Certificate SHA-256: {fingerprint}')
            return
        args = parse_args(remaining + ['--host', '127.0.0.1', '--tls-cert', str(cert), '--tls-key', str(key)])
        args.host = '0.0.0.0'
        args.allowed_host.append(f'{setup.address}:{args.port}')
        if not 1 <= setup.setup_port <= 65535 or setup.setup_port == args.port:
            raise ValueError('Setup port must differ from the HTTPS server port.')
        engine = Engine(args)
        server = create_server(engine)
        device_url = f'https://{setup.address}:{args.port}/phone'
        bootstrap = create_setup_server(setup.address, setup.setup_port, device_url, ca_der, fingerprint,
                                        require_pairing=not args.auto_connect)
        thread = threading.Thread(target=bootstrap.serve_forever, daemon=True)
        thread.start()
        print(f'PC manager: https://127.0.0.1:{args.port}/admin', flush=True)
        print(f'Device setup: http://{setup.address}:{setup.setup_port}/', flush=True)
        print(f'BMO device: {device_url}', flush=True)
        if args.auto_connect:
            print('BMO devices connect automatically on the local network.', flush=True)
        else:
            print(f'Device pairing code: {engine.pair_code}', flush=True)
        print(f'Certificate SHA-256: {fingerprint}', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError, ssl.SSLError) as exc:
        raise SystemExit(str(exc))
    finally:
        if bootstrap:
            if thread:
                bootstrap.shutdown()
                thread.join()
            bootstrap.server_close()
        if server:
            server.server_close()
        if engine:
            engine.close()


if __name__ == '__main__':
    main()
