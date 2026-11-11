from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kiosk.admin_auth import AdminCredentials, hash_password, verify_password


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / '.env.admin'
        self.store = AdminCredentials(self.path)
        self.store.initialize()

    def test_initial_password_and_persistence(self):
        self.assertTrue(self.store.authenticate('1234'))
        with self.assertRaises(ValueError):
            self.store.authenticate('wrong')
        original = self.path.read_bytes()
        self.store.initialize()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertNotIn('ADMIN_PASSWORD=1234', original.decode())
        self.store.change_password('1234', 'New-password-2026', 'New-password-2026')
        reloaded = AdminCredentials(self.path)
        self.assertFalse(reloaded.authenticate('New-password-2026'))
        with self.assertRaises(ValueError):
            reloaded.authenticate('1234')
        self.assertNotIn('New-password-2026', self.path.read_text())

    def test_change_rejects_wrong_current_mismatch_and_short_password(self):
        original = self.path.read_bytes()
        for current, new, confirm in [('wrong', 'LongPassword', 'LongPassword'),
                                      ('1234', 'LongPassword', 'Different'), ('1234', '4567', '4567')]:
            with self.subTest(current=current, new=new):
                with self.assertRaises(ValueError):
                    self.store.change_password(current, new, confirm)
                self.assertEqual(self.path.read_bytes(), original)

    def test_save_failure_preserves_previous_password(self):
        original = self.path.read_bytes()
        with patch('kiosk.admin_auth.os.replace', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.store.change_password('1234', 'LongPassword', 'LongPassword')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(self.store.authenticate('1234'))
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_corrupt_configuration_does_not_reset_to_default(self):
        self.path.write_text('ADMIN_PASSWORD_HASH=invalid\nADMIN_PASSWORD_INITIAL=0\n')
        with self.assertRaises(RuntimeError):
            self.store.initialize()
        self.assertIn('invalid', self.path.read_text())

    def test_unique_salts_and_hash_validation(self):
        first, second = hash_password('same password'), hash_password('same password')
        self.assertNotEqual(first, second)
        self.assertTrue(verify_password('same password', first))
        self.assertFalse(verify_password('different', first))
        with self.assertRaises(ValueError):
            verify_password('same password', 'scrypt$999999999999$8$1$aa$bb')

    def test_cancelled_login_does_not_launch_admin_screens(self):
        import app
        for mode in ('launcher', 'kitchen'):
            with patch('sys.argv', ['app.py', '--mode', mode]), \
                 patch('kiosk.clients.admin.require_login', return_value=False), \
                 patch('kiosk.launcher.run_launcher') as launch, \
                 patch('kiosk.clients.kitchen.KitchenWindow') as kitchen:
                app.main()
                launch.assert_not_called()
                kitchen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
