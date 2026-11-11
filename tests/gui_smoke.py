"""실제 Tk 창을 잠시 띄우는 수동 실행 검증. 네트워크·운영 DB는 사용하지 않는다.

python tests/gui_smoke.py coffee|gimbap|kitchen|launcher
"""
from pathlib import Path
import sys
import time
import subprocess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
from kiosk.clients.base import BaseKiosk
from kiosk.clients.coffee import BodasuCoffeeKiosk
from kiosk.clients.gimbap import GimbapKiosk
from kiosk.clients.kitchen import KitchenWindow
from kiosk.storage.seed import INITIAL_MENUS

output = Path(__file__).resolve().parents[1] / 'logs' / 'ui-review'
output.mkdir(parents=True, exist_ok=True)


def pump(root):
    until = time.monotonic() + 0.35
    while time.monotonic() < until:
        root.update()
        time.sleep(0.01)


def snapshot(root, name):
    root.attributes('-topmost', True)
    root.lift()
    pump(root)
    w, h = root.winfo_width(), root.winfo_height()
    destination = str(output / (name + '.png')).replace("'", "''")
    x, y = root.winfo_rootx(), root.winfo_rooty()
    script = f"Add-Type -AssemblyName System.Drawing; $b = New-Object System.Drawing.Bitmap({w}, {h}); $g = [System.Drawing.Graphics]::FromImage($b); $g.CopyFromScreen({x}, {y}, 0, 0, $b.Size); $b.Save('{destination}'); $g.Dispose(); $b.Dispose()"
    process = subprocess.Popen(['powershell', '-NoProfile', '-Command', script], creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 15
    while process.poll() is None and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    assert process.wait(timeout=2) == 0
    root.attributes('-topmost', False)


def widgets(root):
    for child in root.winfo_children():
        yield child
        yield from widgets(child)


def click(root, text):
    for widget in widgets(root):
        if isinstance(widget, ctk.CTkButton) and widget.cget('text') == text:
            assert widget.winfo_ismapped(), text
            widget.invoke()
            return
    raise AssertionError(f'Button not found: {text}')


def menus(store):
    return [dict(menu_id=i, store_id=s, category=c, menu_name=n, price=p)
            for i, (s, c, n, p) in enumerate(INITIAL_MENUS, 1) if s == store]


def run(mode):
    if mode == 'launcher':
        from kiosk import launcher
        def inspect(root, *args, **kwargs):
            pump(root)
            snapshot(root, mode)
        with patch.object(launcher, 'server_available', return_value=True), patch.object(ctk.CTk, 'mainloop', inspect):
            launcher.run_launcher()
        return
    errors = []
    if mode == 'kitchen':
        with patch('kiosk.clients.kitchen.threading.Thread'):
            root = KitchenWindow()
        root.report_callback_exception = lambda *args: errors.append(args)
        orders = []
        for index, (store, name, state) in enumerate([('KIOSK_01', '보다수 커피', 'PENDING'), ('KIOSK_02', '김밥천국', 'COOKING')], 41):
            item = menus(store)[0]
            item.update(quantity=2, temperature='ICE' if store == 'KIOSK_01' else None,
                        exclude_carrot='당근제외' if store == 'KIOSK_02' else None)
            orders.append(dict(order_id=index, store_id=store, store_name=name, status=state,
                order_type='포장', spoon_needed='수저필요없음', order_time='2026-11-11 12:30:00', total_price=6000, items=[item]))
        root.results.put(('orders', orders))
        pump(root)
        snapshot(root, mode)
        root.change_status('41', 'accept')
        assert root.commands.get_nowait() == (41, 'accept')
        root.store_filter.set('김밥천국')
        root.render_orders()
    else:
        cls = BodasuCoffeeKiosk if mode == 'coffee' else GimbapKiosk
        with patch.object(BaseKiosk, 'load_menus'):
            root = cls()
        root.report_callback_exception = lambda *args: errors.append(args)
        root.results.put(('menus', menus(root.store_id)))
        pump(root)
        root.open_options(root.menus[0])
        pump(root)
        snapshot(root.dialog, mode + '-options')
        click(root.dialog, '선택한 메뉴 담기')
        assert root.cart[0]['quantity'] == 1
        root.change_qty(0, 1)
        assert root.cart[0]['quantity'] == 2
        snapshot(root, mode)
        root.confirm_order()
        pump(root)
        snapshot(root.dialog, mode + '-confirm')
        with patch.object(root, '_request') as request:
            click(root.dialog, '주문 접수하기')
            pump(root)
            request.assert_called_once()
        root.results.put(('order', {'order_id': 42, 'total_price': 6000}))
        pump(root)
        assert not root.cart and not root.busy
        snapshot(root.dialog, mode + '-success')
        root.dialog.destroy()
        root.geometry('1024x700')
        pump(root)
        assert root.order_btn.winfo_rooty() + root.order_btn.winfo_height() <= root.winfo_rooty() + root.winfo_height()
    root.close()
    assert not errors, errors


if __name__ == '__main__':
    run(sys.argv[1])
    print('GUI smoke passed:', sys.argv[1])
