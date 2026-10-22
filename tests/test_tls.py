"""Optional integration check: trusts a temporary CA only in this client context."""
import datetime
import ipaddress
import json
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from bmo.app import Engine, create_server, parse_args
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@unittest.skipUnless(HAS_CRYPTO, "Optional TLS test requires cryptography")
class TLSTests(unittest.TestCase):
    def test_trusted_https_pair_and_chat(self):
        with tempfile.TemporaryDirectory() as directory:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "BMO ephemeral test")])
            now = datetime.datetime.now(datetime.timezone.utc)
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                    .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1))
                    .not_valid_after(now+datetime.timedelta(days=1))
                    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                    .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),critical=False)
                    .sign(key, hashes.SHA256()))
            certfile, keyfile = Path(directory)/"cert.pem", Path(directory)/"key.pem"
            certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            args = parse_args(["--tls-cert",str(certfile),"--tls-key",str(keyfile)])
            args.port = 0
            engine = Engine(args)
            server = create_server(engine)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            context = ssl.create_default_context(cafile=str(certfile))
            url = f"https://127.0.0.1:{server.server_port}"
            try:
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    urllib.request.urlopen(url+"/api/state", context=context)
                self.assertEqual(failure.exception.code, 401)
                req = urllib.request.Request(url+"/api/pair",data=json.dumps({"code":engine.pair_code}).encode(),headers={"Origin":url})
                with urllib.request.urlopen(req,context=context) as response:
                    cookie = response.headers["Set-Cookie"].split(";",1)[0]
                req = urllib.request.Request(url+"/api/chat",data=json.dumps({"question":"안녕"}).encode(),
                    headers={"Origin":url,"Cookie":cookie,"X-BMO-Token":engine.token})
                with urllib.request.urlopen(req,context=context) as response:
                    self.assertTrue(json.load(response)["mock"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == "__main__":
    unittest.main()
