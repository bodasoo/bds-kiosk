import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from kiosk.clients.kitchen import KitchenWindow, order_details


class KitchenTests(unittest.TestCase):
    def test_details_preserve_options(self):
        text = order_details(dict(order_id=1, store_name='커피', order_type='포장', spoon_needed='수저필요함', order_time='12:00', total_price=6000,
                                  items=[dict(menu_name='라떼', quantity=2, temperature='HOT', exclude_carrot=None, exclude_cucumber=None)]))
        self.assertIn('라떼 × 2  (HOT)', text)
        self.assertIn('6,000원', text)

    def test_action_guard_and_duplicate_click(self):
        fake = SimpleNamespace(orders={'1': {'order_id': 1, 'status': 'PENDING'}}, busy=False, online=True, commands=queue.Queue(), render_orders=Mock())
        KitchenWindow.change_status(fake, '1', 'complete')
        self.assertTrue(fake.commands.empty())
        KitchenWindow.change_status(fake, '1', 'accept')
        KitchenWindow.change_status(fake, '1', 'accept')
        self.assertEqual(fake.commands.get_nowait(), (1, 'accept'))
        self.assertTrue(fake.commands.empty())

    def test_worker_updates_then_polls_and_reports_failure(self):
        for failed in (False, True):
            fake = SimpleNamespace(stopped=Mock(), commands=queue.Queue(), results=queue.Queue())
            fake.stopped.is_set.side_effect = [False, True]
            fake.commands.put((12, 'accept'))
            with patch('kiosk.clients.kitchen.request_json', return_value=[]) as request:
                if failed:
                    import requests
                    request.side_effect = requests.ConnectionError('offline')
                KitchenWindow.worker(fake)
                request.assert_any_call('PATCH', '/orders/12/accept')
                kind, value = fake.results.get_nowait()
                self.assertEqual(kind, 'error' if failed else 'orders')
                self.assertEqual(fake.results.get_nowait(), ('done', None))


if __name__ == '__main__':
    unittest.main()
