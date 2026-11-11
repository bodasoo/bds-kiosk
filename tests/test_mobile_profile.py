import plistlib
import tempfile
import unittest
from cryptography import x509
from kiosk.mobile_demo import prepare_certificates, certificate_profile


class MobileProfileTests(unittest.TestCase):
    def test_profile_contains_only_existing_public_root_and_is_stable(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, ca = prepare_certificates('192.168.1.20', folder)
            original = ca.read_bytes()
            encoded = certificate_profile(ca)
            profile = plistlib.loads(encoded)
            self.assertEqual(profile['PayloadType'], 'Configuration')
            self.assertEqual(len(profile['PayloadContent']), 1)
            root = profile['PayloadContent'][0]
            self.assertEqual(root['PayloadType'], 'com.apple.security.root')
            self.assertEqual(root['PayloadContent'], original)
            certificate = x509.load_der_x509_certificate(root['PayloadContent'])
            self.assertTrue(certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
            prepare_certificates('192.168.1.21', folder)
            self.assertEqual(certificate_profile(ca), encoded)
            self.assertEqual(ca.read_bytes(), original)
