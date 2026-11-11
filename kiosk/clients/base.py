"""터치 메뉴, 옵션 선택, 장바구니, 주문 확인과 접수 완료 화면."""
import queue
import threading
import tkinter as tk
import customtkinter as ctk
import requests
from .api import request_json
from . import cart as cart_data
from .ui import BG, WHITE, MUTED, LINE, GREEN, ORANGE, Dialog, button, label, segments, menu_art, setup_window


class BaseKiosk(ctk.CTk):
    def __init__(self, store_id, store_name):
        super().__init__()
        self.store_id, self.store_name = store_id, store_name
        self.coffee = store_id == 'KIOSK_01'
        self.accent = GREEN if self.coffee else ORANGE
        setup_window(self, store_name)
        self.cart, self.menus = [], []
        self.busy = False
        self.results = queue.Queue()
        self.order_type_var = tk.StringVar(value='포장' if self.coffee else '매장식사')
        self.spoon_var = tk.StringVar(value='수저필요없음')
        self.category = tk.StringVar(value='전체')
        self._columns = 0
        self._layout_timer = None
        self.dialog = None
        self.protocol('WM_DELETE_WINDOW', self.close)
        self._build_ui()
        self.load_menus()
        self.timer = self.after(100, self.drain_results)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, minsize=350)
        self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=0)
        header.grid(row=0, column=0, columnspan=2, sticky='ew')
        label(header, 'BODASU / COFFEE' if self.coffee else 'GIMBAP / KITCHEN', 13, self.accent, True).pack(side='left', padx=26, pady=16)
        label(header, self.store_name, 24, bold=True).pack(side='left')
        button(header, '전체화면  F11', lambda: self.attributes('-fullscreen', not self.attributes('-fullscreen')), secondary=True, width=150, height=40).pack(side='right', padx=24)
        left = ctk.CTkFrame(self, fg_color='transparent')
        left.grid(row=1, column=0, sticky='nsew', padx=(24, 16), pady=14)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(3, weight=1)
        banner = ctk.CTkFrame(left, fg_color='#E6EEE4' if self.coffee else '#F5EADD', corner_radius=20)
        banner.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        label(banner, '오늘도, 기분 좋은 한 잔.' if self.coffee else '든든한 한 끼, 정성껏 준비할게요.', 24, self.accent, True).pack(anchor='w', padx=24, pady=(12, 2))
        label(banner, '메뉴를 선택하고 나만의 옵션을 더해보세요.', 14, MUTED).pack(anchor='w', padx=24, pady=(0, 12))
        self.categories = ctk.CTkFrame(left, fg_color='transparent')
        self.categories.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        self.menu_status = label(left, '메뉴를 불러오고 있어요.', 14, MUTED, anchor='w')
        self.menu_status.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        self.menu_grid = ctk.CTkScrollableFrame(left, fg_color='transparent', corner_radius=0)
        self.menu_grid.grid(row=3, column=0, sticky='nsew')
        self.menu_grid.bind('<Configure>', self._schedule_layout)
        self.reload_btn = button(left, '메뉴 다시 불러오기', self.load_menus, secondary=True, height=36)
        self.reload_btn.grid(row=4, column=0, sticky='ew', pady=(8, 0))
        self.reload_btn.grid_remove()
        self._build_checkout()
        label(self, '01 메뉴 선택     →     02 주문 확인     →     03 접수 완료', 13, MUTED).grid(row=2, column=0, columnspan=2, pady=(0, 12))

    def _build_checkout(self):
        panel = ctk.CTkFrame(self, fg_color=WHITE, corner_radius=20, width=350)
        panel.grid(row=1, column=1, sticky='nsew', padx=(0, 24), pady=20)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)
        top = ctk.CTkFrame(panel, fg_color='transparent')
        top.grid(row=0, column=0, sticky='ew', padx=20, pady=(14, 8))
        self.cart_count = label(top, '내 주문  0', 22, bold=True)
        self.cart_count.pack(side='left')
        button(top, '비우기', self.confirm_clear, secondary=True, width=65, height=36, font=('Malgun Gothic', 13)).pack(side='right')
        segments(panel, ['매장식사', '포장'], self.order_type_var, self.accent).grid(row=1, column=0, sticky='ew', padx=20, pady=(0, 12))
        self.cart_list = ctk.CTkScrollableFrame(panel, fg_color='transparent', width=300)
        self.cart_list.grid(row=2, column=0, sticky='nsew', padx=12)
        bottom = ctk.CTkFrame(panel, fg_color='transparent')
        bottom.grid(row=3, column=0, sticky='ew', padx=20, pady=12)
        ctk.CTkSwitch(bottom, text='수저 / 티스푼 필요해요', variable=self.spoon_var, onvalue='수저필요함', offvalue='수저필요없음', progress_color=self.accent, font=('Malgun Gothic', 14), text_color=MUTED).pack(anchor='w', pady=(0, 12))
        label(bottom, '주문 합계', 14, MUTED, height=20).pack(anchor='w')
        self.total_lbl = label(bottom, '0원', 28, self.accent, True)
        self.total_lbl.pack(anchor='w', pady=(0, 6))
        self.order_btn = button(bottom, '주문 확인하기', self.confirm_order, color=self.accent, height=60)
        self.order_btn.pack(fill='x')
        self._refresh_cart_ui()

    def _schedule_layout(self, event=None):
        if self._layout_timer:
            self.after_cancel(self._layout_timer)
        self._layout_timer = self.after(120, self._resize_cards)

    def _resize_cards(self):
        self._layout_timer = None
        columns = max(1, min(4, int(self.menu_grid.winfo_width() / self.menu_grid._get_widget_scaling()) // 220))
        if columns != self._columns:
            self._columns = columns
            self.render_menus()

    def load_menus(self):
        self.reload_btn.configure(state='disabled')
        self.menu_status.configure(text='메뉴를 불러오고 있어요.')
        threading.Thread(target=self._request, args=('menus', 'GET', f'/menus/{self.store_id}', None), daemon=True).start()

    def _request(self, kind, method, path, payload):
        try:
            self.results.put((kind, request_json(method, path, payload)))
        except (requests.RequestException, ValueError):
            self.results.put((kind + '_error', None))

    def drain_results(self):
        try:
            while True:
                kind, data = self.results.get_nowait()
                if kind == 'menus':
                    self.menus = data
                    self.reload_btn.grid_remove()
                    self.reload_btn.configure(state='normal')
                    for widget in self.categories.winfo_children():
                        widget.destroy()
                    values = ['전체'] + list(dict.fromkeys(m['category'] for m in data))
                    segments(self.categories, values, self.category, self.accent, lambda _: self.render_menus()).pack(fill='x')
                    self.render_menus()
                elif kind == 'menus_error':
                    self.reload_btn.grid()
                    self.menu_status.configure(text='메뉴를 불러오지 못했어요. 잠시 후 다시 시도해주세요.', text_color=ORANGE)
                    self.reload_btn.configure(state='normal')
                elif kind == 'order':
                    self.busy = False
                    self.cart.clear()
                    self._refresh_cart_ui()
                    self.show_success(data)
                elif kind == 'order_error':
                    self.busy = False
                    self._refresh_cart_ui()
                    self.show_order_error()
        except queue.Empty:
            pass
        self.timer = self.after(100, self.drain_results)

    def render_menus(self):
        for widget in self.menu_grid.winfo_children():
            widget.destroy()
        columns = self._columns or 2
        for i in range(4):
            self.menu_grid.grid_columnconfigure(i, weight=1 if i < columns else 0, uniform='cards' if i < columns else '')
        menus = [m for m in self.menus if self.category.get() in ('전체', m['category'])]
        self.menu_status.configure(text=f'{self.category.get()} 메뉴  ·  {len(menus)}가지', text_color=MUTED)
        for index, menu in enumerate(menus):
            card = ctk.CTkFrame(self.menu_grid, fg_color=WHITE, corner_radius=16, border_width=1, border_color=LINE)
            card.grid(row=index // columns, column=index % columns, sticky='nsew', padx=5, pady=6)
            callback = lambda m=menu: self.open_options(m)
            menu_art(card, menu['category'], menu['menu_name'], self.accent, callback).pack(padx=8, pady=(14, 8))
            title = label(card, menu['menu_name'], 17, bold=True, wraplength=180)
            title.pack(padx=8)
            title.bind('<Button-1>', lambda event, m=menu: self.open_options(m))
            label(card, f"{menu['price']:,}원", 18, self.accent, True).pack(pady=(2, 10))
            button(card, '담기  +', callback, color=self.accent, height=42).pack(fill='x', padx=12, pady=(0, 12))

    def _new_dialog(self, title, height=540):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.destroy()
        self.dialog = Dialog(self, title, height)
        return self.dialog

    def open_options(self, menu):
        if self.busy:
            return
        dialog = self._new_dialog('메뉴 옵션 선택')
        label(dialog, '나만의 메뉴 만들기', 14, MUTED).pack(pady=(22, 4))
        label(dialog, menu['menu_name'], 26, bold=True, wraplength=450).pack()
        label(dialog, f"{menu['price']:,}원", 20, self.accent, True).pack(pady=(4, 18))
        temperature = tk.StringVar(dialog, value='ICE')
        carrot, cucumber = tk.BooleanVar(dialog), tk.BooleanVar(dialog)
        quantity = tk.IntVar(dialog, value=1)
        if self.coffee:
            label(dialog, '음료 온도를 선택해주세요', 16).pack(pady=8)
            segments(dialog, ['ICE', 'HOT'], temperature, self.accent).pack(fill='x', padx=32, pady=8)
        elif menu['category'] == '김밥류':
            label(dialog, '빼고 싶은 재료가 있나요?', 16).pack(pady=8)
            for text, variable in [('당근 빼주세요', carrot), ('오이 빼주세요', cucumber)]:
                ctk.CTkCheckBox(dialog, text=text, variable=variable, fg_color=self.accent, font=('Malgun Gothic', 17), height=40).pack(anchor='w', padx=60, pady=5)
        else:
            label(dialog, '기본 조리로 준비해드려요.', 17, MUTED).pack(pady=26)
        qty_row = ctk.CTkFrame(dialog, fg_color='transparent')
        qty_row.pack(pady=24)
        button(qty_row, '−', lambda: quantity.set(max(1, quantity.get()-1)), secondary=True, width=56).pack(side='left')
        label(qty_row, '', 23, bold=True, textvariable=quantity, width=90).pack(side='left')
        button(qty_row, '+', lambda: quantity.set(min(99, quantity.get()+1)), secondary=True, width=56).pack(side='left')

        def add():
            options = {'temperature': temperature.get()} if self.coffee else {'exclude_carrot': '당근제외' if carrot.get() else '당근포함', 'exclude_cucumber': '오이제외' if cucumber.get() else '오이포함'}
            cart_data.add_item(self.cart, menu, options, quantity.get())
            dialog.destroy()
            self._refresh_cart_ui()

        button(dialog, '선택한 메뉴 담기', add, color=self.accent, height=56).pack(side='bottom', fill='x', padx=32, pady=(8, 24))
        button(dialog, '돌아가기', dialog.destroy, secondary=True).pack(side='bottom', fill='x', padx=32)

    def _refresh_cart_ui(self):
        for widget in self.cart_list.winfo_children():
            widget.destroy()
        if not self.cart:
            label(self.cart_list, '아직 담은 메뉴가 없어요\n먹고 싶은 메뉴를 선택해주세요.', 16, MUTED, justify='center').pack(pady=60)
        for index, item in enumerate(self.cart):
            row = ctk.CTkFrame(self.cart_list, fg_color=BG, corner_radius=12)
            row.pack(fill='x', pady=5)
            label(row, item['menu_name'], 16, bold=True, wraplength=280, anchor='w').pack(fill='x', padx=12, pady=(10, 0))
            label(row, cart_data.option_text(item), 12, MUTED, wraplength=280, anchor='w').pack(fill='x', padx=12)
            controls = ctk.CTkFrame(row, fg_color='transparent')
            controls.pack(fill='x', padx=10, pady=10)
            for text, delta in [('−', -1), ('+', 1)]:
                button(controls, text, lambda i=index, d=delta: self.change_qty(i, d), secondary=True, width=42, height=42).pack(side='left', padx=2)
                if delta == -1:
                    label(controls, str(item['quantity']), 16, bold=True, width=32).pack(side='left')
            label(controls, f"{item['price'] * item['quantity']:,}원", 15, bold=True).pack(side='right')
        self.cart_count.configure(text=f"내 주문  {sum(i['quantity'] for i in self.cart)}")
        self.total_lbl.configure(text=f'{cart_data.total(self.cart):,}원')
        self.order_btn.configure(state='normal' if self.cart and not self.busy else 'disabled', text='주문 접수 중…' if self.busy else '주문 확인하기')

    def change_qty(self, index, delta):
        if self.busy:
            return
        self.cart[index]['quantity'] += delta
        if self.cart[index]['quantity'] <= 0:
            del self.cart[index]
        self._refresh_cart_ui()

    def confirm_clear(self):
        if not self.cart or self.busy:
            return
        dialog = self._new_dialog('주문 비우기', 260)
        label(dialog, '담은 메뉴를 모두 비울까요?', 24, bold=True).pack(pady=32)
        button(dialog, '모두 비우기', lambda: (self.clear_cart(), dialog.destroy()), color=self.accent).pack(fill='x', padx=32, pady=5)
        button(dialog, '계속 주문하기', dialog.destroy, secondary=True).pack(fill='x', padx=32, pady=5)

    def clear_cart(self):
        if not self.busy:
            self.cart.clear()
            self._refresh_cart_ui()

    def confirm_order(self):
        if not self.cart or self.busy:
            return
        dialog = self._new_dialog('주문 최종 확인', 620)
        label(dialog, '주문 내용을 확인해주세요', 25, bold=True).pack(pady=(24, 5))
        label(dialog, f'{self.order_type_var.get()}  ·  {self.spoon_var.get()}', 16, self.accent, True).pack(pady=8)
        listing = ctk.CTkScrollableFrame(dialog, fg_color=BG, height=230)
        listing.pack(fill='both', expand=True, padx=28, pady=10)
        for item in self.cart:
            label(listing, f"{item['menu_name']}  × {item['quantity']}\n{cart_data.option_text(item)}", 16, anchor='w', justify='left', wraplength=390).pack(fill='x', padx=10, pady=9)
        label(dialog, f'합계  {cart_data.total(self.cart):,}원', 28, self.accent, True).pack(pady=10)
        label(dialog, '주문 접수용 화면입니다. 실제 결제는 진행되지 않습니다.', 12, MUTED).pack(pady=4)
        button(dialog, '주문 접수하기', self.submit_order_async, color=self.accent, height=54).pack(fill='x', padx=28, pady=8)
        button(dialog, '수정하기', dialog.destroy, secondary=True).pack(fill='x', padx=28, pady=(0, 22))

    def submit_order_async(self):
        if not self.cart or self.busy:
            return
        self.busy = True
        payload = cart_data.order_payload(self.cart, self.store_id, self.store_name, self.order_type_var.get(), self.spoon_var.get())
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.destroy()
        self._refresh_cart_ui()
        threading.Thread(target=self._request, args=('order', 'POST', '/order', payload), daemon=True).start()

    def show_success(self, data):
        dialog = self._new_dialog('주문 접수 완료', 460)
        label(dialog, '주문이 접수되었어요', 28, self.accent, True).pack(pady=(35, 12))
        label(dialog, '주문 번호', 16, MUTED).pack()
        label(dialog, data.get('order_number', f"{data['order_id']:03}"), 80, self.accent, True).pack(pady=10)
        label(dialog, '준비가 완료되면 주문 번호로 안내해드릴게요.\n주문 번호를 기억해주세요.', 17, justify='center').pack(pady=12)
        button(dialog, '확인 · 새로운 주문', dialog.destroy, color=self.accent, height=56).pack(fill='x', padx=32, pady=24)
        self.order_type_var.set('포장' if self.coffee else '매장식사')
        self.spoon_var.set('수저필요없음')

    def show_order_error(self):
        dialog = self._new_dialog('주문 확인 필요', 340)
        label(dialog, '주문 결과를 확인하지 못했어요', 23, ORANGE, True).pack(pady=(32, 15))
        label(dialog, '중복 주문을 피하려면 직원에게 접수 여부를\n먼저 확인해주세요. 담은 메뉴는 유지됩니다.', 17, justify='center').pack(pady=18)
        button(dialog, '확인', dialog.destroy, color=self.accent).pack(fill='x', padx=32, pady=24)

    def close(self):
        self.after_cancel(self.timer)
        if self._layout_timer:
            self.after_cancel(self._layout_timer)
        self.destroy()
