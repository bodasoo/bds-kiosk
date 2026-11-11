from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from unittest.mock import patch
import requests
from kiosk.certificates import generate_self_signed_cert
from kiosk.mobile_demo import prepare_certificates
from kiosk.clients.api import request_json


class TLSTests(unittest.TestCase):
    def test_both_demo_modes_verify_server_and_reject_untrusted_certificate(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cert, key = root/'cert.pem', root/'key.pem'
            generate_self_signed_cert(str(cert), str(key))
            mobile_cert, mobile_key, ca = prepare_certificates('192.168.1.20', root/'mobile')
            for server_cert, server_key, trust, wrong_trust in (
                (cert, key, cert, ca.parent/'ca.pem'),
                (mobile_cert, mobile_key, ca.parent/'ca.pem', cert),
            ):
                server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(server_cert, server_key)
                server.socket = context.wrap_socket(server.socket, server_side=True)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    with patch('kiosk.clients.api.BASE_URL', f'https://127.0.0.1:{server.server_port}'):
                        with patch('kiosk.clients.api.SSL_CA_FILE', str(trust)):
                            self.assertEqual(request_json('GET','/health'), {'ok':True})
                        with patch('kiosk.clients.api.SSL_CA_FILE', str(wrong_trust)):
                            with self.assertRaises(requests.exceptions.SSLError):
                                request_json('GET','/health')
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()
