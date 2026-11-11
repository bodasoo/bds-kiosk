"""주방 보드. 작업 스레드는 API만 호출하고 after 큐에서 화면을 갱신한다."""
import queue
import threading
import tkinter as tk
from datetime import datetime
import customtkinter as ctk
import requests
from kiosk.config import POLLING_INTERVAL_SEC
from .api import request_json
from .cart import option_text
from .ui import BG, WHITE, MUTED, GREEN, ORANGE, label, button, segments, setup_window


def order_details(order):
    lines = [f"주문 #{order.get('order_number', order['order_id'])} · {order['store_name']}",
             f"{order['order_type']} / {order['spoon_needed']}", order['order_time'], '']
    for item in order['items']:
        lines.append(f"{item['menu_name']} × {item['quantity']}  ({option_text(item)})")
    lines.append(f"\n합계 {order['total_price']:,}원")
    return '\n'.join(lines)


class KitchenWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        setup_window(self, '주방 종합창 · BODASU OPERATIONS')
        self.orders = {}
        self.busy = False
        self.online = False
        self.results, self.commands = queue.Queue(), queue.Queue()
        self.stopped = threading.Event()
        self.store_filter = tk.StringVar(value='전체 매장')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self._build_ui()
        threading.Thread(target=self.worker, daemon=True).start()
        self.timer = self.after(100, self.drain_results)

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0)
        header.pack(fill='x')
        label(header, 'BODASU  /  OPERATIONS', 13, GREEN, True).pack(side='left', padx=28, pady=25)
        label(header, '주방 종합창', 26, bold=True).pack(side='left')
        button(header, '전체화면  F11', lambda: self.attributes('-fullscreen', not self.attributes('-fullscreen')), secondary=True, width=150, height=40).pack(side='right', padx=24)
        bar = ctk.CTkFrame(self, fg_color='transparent')
        bar.pack(fill='x', padx=28, pady=(20, 12))
        segments(bar, ['전체 매장', '보다수 커피', '김밥천국'], self.store_filter, command=lambda _: self.render_orders()).pack(side='left')
        self.status = label(bar, '서버 연결 중…', 14, MUTED)
        self.status.pack(side='right')
        self.summary = label(self, '새 주문을 기다리고 있습니다.', 16, MUTED, anchor='w')
        self.summary.pack(fill='x', padx=28, pady=(0, 16))
        board = ctk.CTkFrame(self, fg_color='transparent')
        board.pack(fill='both', expand=True, padx=24, pady=(0, 22))
        board.grid_columnconfigure((0, 1), weight=1, uniform='lanes')
        board.grid_rowconfigure(0, weight=1)
        self.lanes, self.counts = {}, {}
        for column, (status, title, color) in enumerate([('PENDING', '접수 대기', ORANGE), ('COOKING', '조리 중', GREEN)]):
            lane = ctk.CTkFrame(board, fg_color='#EEEFE9', corner_radius=18)
            lane.grid(row=0, column=column, sticky='nsew', padx=6)
            self.counts[status] = label(lane, f'{title}  0', 24, color, True, anchor='w')
            self.counts[status].pack(fill='x', padx=20, pady=18)
            self.lanes[status] = ctk.CTkScrollableFrame(lane, fg_color='transparent')
            self.lanes[status].pack(fill='both', expand=True, padx=8, pady=(0, 10))
        self.render_orders()

    def worker(self):
        while not self.stopped.is_set():
            action = None
            try:
                action = self.commands.get_nowait()
            except queue.Empty:
                pass
            try:
                if action:
                    order_id, operation = action
                    request_json('PATCH', f'/orders/{order_id}/{operation}')
                self.results.put(('orders', request_json('GET', '/orders/kitchen')))
            except (requests.RequestException, ValueError):
                self.results.put(('error', '연결 끊김 · 자동 재연결 중 (마지막 조회 내용)'))
            if action:
                self.results.put(('done', None))
            self.stopped.wait(POLLING_INTERVAL_SEC)

    def drain_results(self):
        changed = False
        try:
            while True:
                kind, value = self.results.get_nowait()
                if kind == 'orders':
                    orders = {str(order['order_id']): order for order in value}
                    changed = changed or orders != self.orders or not self.online
                    self.orders, self.online = orders, True
                    self.status.configure(text='● 연결됨  ·  ' + datetime.now().strftime('%H:%M:%S'), text_color=GREEN)
                elif kind == 'error':
                    changed = changed or self.online
                    self.online = False
                    self.status.configure(text=value, text_color=ORANGE)
                elif kind == 'done':
                    self.busy = False
                    changed = True
        except queue.Empty:
            pass
        if changed:
            self.render_orders()
        self.timer = self.after(100, self.drain_results)

    def render_orders(self):
        orders = [o for o in self.orders.values() if self.store_filter.get() in ('전체 매장', o['store_name'])]
        self.summary.configure(text=f"현재 주문 {len(orders)}건  ·  {'처리 중입니다…' if self.busy else '접수 후 조리를 시작하고, 준비가 끝나면 완료해주세요.'}")
        for state, lane in self.lanes.items():
            # 데이터가 바뀔 때만 다시 그려 스크롤과 읽기 흐름을 유지한다.
            position = lane._parent_canvas.yview()[0]
            for widget in lane.winfo_children():
                widget.destroy()
            matching = [o for o in orders if o['status'] == state]
            title = '접수 대기' if state == 'PENDING' else '조리 중'
            self.counts[state].configure(text=f'{title}  {len(matching)}')
            if not matching:
                label(lane, '대기 중인 주문이 없습니다.' if state == 'PENDING' else '조리 중인 주문이 없습니다.', 18, MUTED).pack(pady=70)
            for order in matching:
                self._order_card(lane, order)
            lane._parent_canvas.yview_moveto(position)

    def _order_card(self, parent, order):
        color = GREEN if order['store_id'] == 'KIOSK_01' else ORANGE
        card = ctk.CTkFrame(parent, fg_color=WHITE, corner_radius=16)
        card.pack(fill='x', padx=4, pady=(0, 12))
        top = ctk.CTkFrame(card, fg_color='transparent')
        top.pack(fill='x', padx=20, pady=(16, 8))
        number = order.get('order_number', f"{order['order_id']:03}")
        label(top, f"#{number}", 32, bold=True).pack(side='left')
        label(top, order['store_name'], 15, color, True).pack(side='right')
        label(card, f"{order['order_type']}  ·  {order['spoon_needed']}  ·  {order['order_time'][11:16]}", 13, MUTED, anchor='w').pack(fill='x', padx=20, pady=(0, 12))
        for item in order['items']:
            label(card, f"{item['menu_name']}  × {item['quantity']}", 20, bold=True, anchor='w', wraplength=400).pack(fill='x', padx=20, pady=(4, 0))
            label(card, option_text(item), 14, color, anchor='w', wraplength=400).pack(fill='x', padx=20, pady=(0, 6))
        action = 'accept' if order['status'] == 'PENDING' else 'complete'
        button(card, '주문 접수 · 조리 시작' if action == 'accept' else '조리 완료 · 픽업 알림',
               lambda oid=str(order['order_id']), op=action: self.change_status(oid, op),
               color=ORANGE if action == 'accept' else GREEN, height=54,
               state='normal' if self.online and not self.busy else 'disabled').pack(fill='x', padx=18, pady=(12, 18))

    def change_status(self, order_id, action):
        order = self.orders.get(str(order_id))
        required = {'accept': 'PENDING', 'complete': 'COOKING'}
        if not order or self.busy or not self.online or order['status'] != required.get(action):
            return
        self.busy = True
        self.commands.put((order['order_id'], action))
        self.render_orders()

    def close(self):
        self.stopped.set()
        self.after_cancel(self.timer)
        self.destroy()
