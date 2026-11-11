import base64
from contextlib import ExitStack, closing
import json
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch, Mock
from uuid import uuid4
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from kiosk.server import app
from kiosk.config import DEFAULT_HEADERS
from kiosk.storage.connection import get_db_connection
from kiosk.storage.setup import init_db
from kiosk.push import validate_subscription, deliver_one


class MobileTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        folder = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch('kiosk.storage.connection.SQLITE_DB_PATH', str(Path(folder)/'test.db')))
        self.stack.enter_context(patch.dict('os.environ', {'BDS_DISABLE_PUSH_WORKER':'1'}))
        self.client = self.stack.enter_context(TestClient(app))
        self.headers = {'X-Customer-Token':secrets.token_urlsafe(32)}
        self.payload = {'request_id':str(uuid4()), 'store_id':'KIOSK_01', 'items':[{'menu_id':1,'quantity':2,'temperature':'ICE'}]}

    def order(self):
        response = self.client.post('/api/mobile/orders', headers=self.headers, json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def subscription(self):
        key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return {'endpoint':'https://web.push.apple.com/test-endpoint', 'keys':{'p256dh':base64.urlsafe_b64encode(key).decode().rstrip('='), 'auth':secrets.token_urlsafe(16)}}

    def test_order_isolation_idempotency_and_authoritative_price(self):
        order = self.order()
        self.assertEqual(order['order_number'], 'A001')
        self.assertEqual(order['total_price'], 6000)
        self.assertEqual(self.order(), order)
        self.assertEqual(self.client.get('/api/mobile/orders', headers={'X-Customer-Token':secrets.token_urlsafe(32)}).json(), [])
        self.assertEqual(self.client.get('/api/mobile/orders').status_code, 401)
        self.assertEqual(len(self.client.get('/api/mobile/orders', headers=self.headers).json()), 1)
        self.payload['items'][0]['quantity'] = 3
        self.assertEqual(self.client.post('/api/mobile/orders', headers=self.headers, json=self.payload).status_code, 409)
        self.payload['request_id'] = str(uuid4())
        self.payload['items'][0]['price'] = 1
        self.assertEqual(self.client.post('/api/mobile/orders', headers=self.headers, json=self.payload).status_code, 422)
        del self.payload['items'][0]['price']
        self.payload['store_id'] = 'KIOSK_02'
        self.assertEqual(self.client.post('/api/mobile/orders', headers=self.headers, json=self.payload).status_code, 400)
        kitchen = self.client.get('/orders/kitchen', headers=DEFAULT_HEADERS).json()
        self.assertEqual(kitchen[0]['order_number'], 'A001')

    def test_push_queue_transition_retry_and_delivery(self):
        subscription = self.subscription()
        self.assertEqual(self.client.post('/api/mobile/push/subscriptions', headers=self.headers, json=subscription).status_code, 200)
        order = self.order()
        path = f"/orders/{order['order_id']}"
        self.assertEqual(self.client.patch(path+'/complete', headers=DEFAULT_HEADERS).status_code, 409)
        for action in ('accept','accept','complete'):
            self.assertEqual(self.client.patch(path+'/'+action, headers=DEFAULT_HEADERS).status_code, 200)
        with closing(get_db_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM push_outbox').fetchone()[0], 2)
        with patch('kiosk.push.webpush', return_value=Mock(status_code=201)) as send:
            self.assertTrue(deliver_one())
            self.assertTrue(deliver_one())
            self.assertFalse(deliver_one())
            self.assertEqual(send.call_count, 2)
            self.assertEqual(json.loads(send.call_args.kwargs['data'])['order_number'], 'A001')
        self.assertEqual(self.client.get('/api/mobile/orders', headers=self.headers).json()[0]['status'], 'COMPLETED')

    def test_bad_push_hosts_and_keys_rejected(self):
        subscription = self.subscription()
        validate_subscription(subscription)
        for endpoint in ('http://web.push.apple.com/a','https://127.0.0.1/a','https://web.push.apple.com.evil.test/a','https://web.push.apple.com:8443/a','https://user@web.push.apple.com/a'):
            with self.assertRaises(ValueError):
                validate_subscription({**subscription,'endpoint':endpoint})
        subscription['keys']['auth'] = 'bad'
        self.assertEqual(self.client.post('/api/mobile/push/subscriptions', headers=self.headers, json=subscription).status_code, 400)

    def test_push_failure_retries_and_expired_subscription_is_removed(self):
        from pywebpush import WebPushException
        subscription = self.subscription()
        self.client.post('/api/mobile/push/subscriptions', headers=self.headers, json=subscription)
        result = self.order()
        self.client.patch(f"/orders/{result['order_id']}/accept", headers=DEFAULT_HEADERS)
        with patch('kiosk.push.webpush', side_effect=TimeoutError):
            self.assertTrue(deliver_one())
        with closing(get_db_connection()) as conn:
            row = conn.execute('SELECT * FROM push_outbox').fetchone()
            self.assertEqual(row['attempts'], 1)
            self.assertIsNone(row['sent_at'])
            self.assertEqual(row['last_error'], 'TimeoutError')
            conn.execute('UPDATE push_outbox SET next_attempt=0')
            conn.commit()
        with patch('kiosk.push.webpush', side_effect=WebPushException('expired', response=Mock(status_code=410))):
            self.assertTrue(deliver_one())
        with closing(get_db_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM push_subscriptions').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM push_outbox').fetchone()[0], 0)

    def test_legacy_schema_migration_preserves_id_and_marks_kiosk(self):
        import sqlite3
        from kiosk.storage.migrations import migrate_mobile
        with closing(sqlite3.connect(':memory:')) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('CREATE TABLE orders(order_id INTEGER PRIMARY KEY, total_price INTEGER)')
            conn.execute('CREATE TABLE order_items(item_id INTEGER PRIMARY KEY)')
            conn.execute('INSERT INTO orders VALUES (42, 3000)')
            migrate_mobile(conn)
            migrate_mobile(conn)
            row = conn.execute('SELECT * FROM orders').fetchone()
            self.assertEqual((row['order_id'],row['total_price'],row['order_source']), (42,3000,'KIOSK'))

    def test_migration_preserves_existing_order(self):
        result = self.order()
        init_db()
        init_db()
        self.assertEqual(self.order(), result)
        with closing(get_db_connection()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0], 1)

    def test_certificates_persist_ca_and_include_lan_ip(self):
        from kiosk.mobile_demo import prepare_certificates
        from cryptography import x509
        import ipaddress
        with tempfile.TemporaryDirectory() as folder:
            cert, key, ca = prepare_certificates('192.168.1.23', folder)
            first = ca.read_bytes()
            leaf = x509.load_pem_x509_certificate(cert.read_bytes())
            ips = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
            self.assertIn(ipaddress.ip_address('192.168.1.23'), ips)
            prepare_certificates('192.168.1.24', folder)
            self.assertEqual(first, ca.read_bytes())
