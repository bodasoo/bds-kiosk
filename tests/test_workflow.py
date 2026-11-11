"""기존 kiosk.db를 건드리지 않는 주문 흐름 및 공통 클라이언트 검증."""
from pathlib import Path
from contextlib import ExitStack
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from kiosk.config import DEFAULT_HEADERS
from kiosk.server import app
from kiosk.clients.base import BaseKiosk
from kiosk.clients.coffee import BodasuCoffeeKiosk
from kiosk.clients.gimbap import GimbapKiosk


class WorkflowTests(unittest.TestCase):
    def test_launcher_reuses_existing_server_without_starting_or_stopping_it(self):
        from kiosk import launcher
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.object(launcher, "BASE_DIR", directory))
            stack.enter_context(patch.object(launcher, "server_available", return_value=True))
            window = stack.enter_context(patch.object(launcher.ctk, "CTk")).return_value
            stack.enter_context(patch.object(launcher, "label"))
            stack.enter_context(patch.object(launcher, "setup_window"))
            stack.enter_context(patch.object(launcher.ctk, "CTkFrame"))
            buttons = stack.enter_context(patch.object(launcher, "button"))
            popen = stack.enter_context(patch.object(launcher.subprocess, "Popen"))

            def mainloop():
                window.after.call_args.args[1]()
                buttons.return_value.configure.assert_called_with(state="normal")
                window.protocol.call_args.args[1]()

            window.mainloop.side_effect = mainloop
            launcher.run_launcher()
            popen.assert_not_called()

    def test_launcher_starts_server_opens_store_and_cleans_up(self):
        from kiosk import launcher
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.object(launcher, "BASE_DIR", directory))
            window = stack.enter_context(patch.object(launcher.ctk, "CTk")).return_value
            stack.enter_context(patch.object(launcher, "label"))
            stack.enter_context(patch.object(launcher, "setup_window"))
            stack.enter_context(patch.object(launcher.ctk, "CTkFrame"))
            buttons = stack.enter_context(patch.object(launcher, "button"))
            popen = stack.enter_context(patch.object(launcher.subprocess, "Popen"))
            server, coffee = Mock(), Mock()
            server.poll.return_value = coffee.poll.return_value = None
            popen.side_effect = [server, coffee]
            stack.enter_context(patch.object(launcher, "server_available", side_effect=[False, True]))

            def mainloop():
                window.after.call_args.args[1]()
                buttons.return_value.configure.assert_called_with(state="normal")
                buttons.call_args_list[0].args[2]()
                window.protocol.call_args.args[1]()

            window.mainloop.side_effect = mainloop
            launcher.run_launcher()
            self.assertEqual(popen.call_args_list[0].args[0][-1], "server")
            self.assertEqual(popen.call_args_list[1].args[0][-1], "coffee")
            for process in (server, coffee):
                process.terminate.assert_called_once()
                process.wait.assert_called_once()

    def test_order_kitchen_notifications_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("kiosk.storage.connection.SQLITE_DB_PATH", str(Path(directory) / "test.db")):
                with TestClient(app) as client:
                    self.assertEqual(client.get("/health").status_code, 200)
                    self.assertEqual(client.get("/menus/KIOSK_01").status_code, 403)
                    for store_id, count, options in (
                        ("KIOSK_01", 12, {"temperature": "ICE"}),
                        ("KIOSK_02", 11, {"exclude_carrot": "당근제외", "exclude_cucumber": "오이포함"}),
                    ):
                        menus = client.get(f"/menus/{store_id}", headers=DEFAULT_HEADERS).json()
                        self.assertEqual(len(menus), count)
                        item = {"menu_name": menus[0]["menu_name"], "price": menus[0]["price"], "quantity": 2, **options}
                        payload = {"store_id": store_id, "store_name": "테스트", "order_type": "포장", "spoon_needed": "수저필요없음", "items": [item]}
                        response = client.post("/order", headers=DEFAULT_HEADERS, json=payload)
                        self.assertEqual(response.status_code, 200, response.text)
                        order = response.json()
                        self.assertEqual(order["total_price"], menus[0]["price"] * 2)
                        order_id = order["order_id"]
                        kitchen = client.get("/orders/kitchen", headers=DEFAULT_HEADERS).json()
                        self.assertEqual(kitchen[0]["status"], "PENDING")
                        for key, value in options.items():
                            self.assertEqual(kitchen[0]["items"][0][key], value)
                        for action, notification in (("accept", "ACCEPTED"), ("complete", "COMPLETED")):
                            self.assertEqual(client.patch(f"/orders/{order_id}/{action}", headers=DEFAULT_HEADERS).status_code, 200)
                            notices = client.get("/orders/notifications", headers=DEFAULT_HEADERS).json()
                            self.assertEqual(notices[0]["notification_type"], notification)
                            self.assertEqual(client.get("/orders/notifications", headers=DEFAULT_HEADERS).json(), [])
                        self.assertEqual(client.get("/orders/kitchen", headers=DEFAULT_HEADERS).json(), [])
                        payload["items"][0]["menu_name"] = "없는 메뉴"
                        self.assertEqual(client.post("/order", headers=DEFAULT_HEADERS, json=payload).status_code, 400)
                        self.assertEqual(client.get("/orders/kitchen", headers=DEFAULT_HEADERS).json(), [])

    def test_shared_cart_and_payload_keep_store_options(self):
        from kiosk.clients.cart import add_item, total, order_payload
        menu = {"menu_name": "테스트", "price": 3000}
        cart = []
        add_item(cart, menu, {"temperature": "HOT"}, 2)
        add_item(cart, menu, {"temperature": "HOT"})
        add_item(cart, menu, {"temperature": "ICE"})
        self.assertEqual([item["quantity"] for item in cart], [3, 1])
        self.assertEqual(total(cart), 12000)
        payload = order_payload(cart, "KIOSK_01", "커피", "포장", "수저필요없음")
        self.assertEqual(payload["items"][0]["temperature"], "HOT")
        self.assertIsNone(payload["items"][0]["exclude_carrot"])
        add_item(cart, menu, {"exclude_carrot": "당근제외", "exclude_cucumber": "오이포함"})
        self.assertEqual(len(cart), 3)

    def test_submit_guard_and_failed_request_preserve_cart(self):
        import queue
        import requests
        fake = SimpleNamespace(cart=[{"menu_name": "테스트", "price": 3000, "quantity": 1}],
            busy=False, store_id="KIOSK_01", store_name="커피", dialog=None,
            order_type_var=Mock(), spoon_var=Mock(), _refresh_cart_ui=Mock(),
            _request=Mock(), results=queue.Queue())
        with patch("kiosk.clients.base.threading.Thread") as thread:
            BaseKiosk.submit_order_async(fake)
            BaseKiosk.submit_order_async(fake)
            self.assertEqual(thread.call_count, 1)
        with patch("kiosk.clients.base.request_json", side_effect=requests.Timeout):
            BaseKiosk._request(fake, "order", "POST", "/order", {})
        self.assertEqual(fake.results.get_nowait(), ("order_error", None))
        self.assertEqual(len(fake.cart), 1)


if __name__ == "__main__":
    unittest.main()
