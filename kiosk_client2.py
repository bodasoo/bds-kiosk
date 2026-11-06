"""
[김밥천국 키오스크 클라이언트 - kiosk_client2.py]
- 매장 코드: KIOSK_02 (김밥천국)
- UI 프레임워크: Python 표준 Tkinter (ttk 스타일 적용)
- 주요 기능:
  1) 카테고리별 메뉴 조회 및 선택 (김밥류 7종, 식사/분식류 4종)
  2) 김밥류 전용 옵션(당근 제외 / 오이 제외 체크박스), 포장/매장식사, 수저 필요 여부 선택
  3) 장바구니 담기, 수량 조절, 삭제 및 실시간 총 결제 금액 계산
  4) 결제 시 UI 멈춤(렉) 방지를 위해 백그라운드 스레드(threading.Thread)로
     중앙 FastAPI 서버에 HTTPS POST /order 요청 전송 (access_token 헤더 포함)
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List
import urllib3
import requests

from config import BASE_URL, DEFAULT_HEADERS
from database import fetch_menus_by_store, init_db

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

STORE_ID = "KIOSK_02"
STORE_NAME = "김밥천국"


class GimbapKiosk(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"🍙 {STORE_NAME} 키오스크 ({STORE_ID})")
        self.geometry("1040x720")
        self.configure(bg="#FFF8E1")
        self.resizable(False, False)

        # DB 초기화 보장 및 메뉴 로드
        init_db()
        self.menus: List[Dict[str, Any]] = fetch_menus_by_store(STORE_ID)

        # 장바구니 리스트
        self.cart: List[Dict[str, Any]] = []

        # 옵션 상태 변수
        self.no_carrot_var = tk.BooleanVar(value=False)
        self.no_cucumber_var = tk.BooleanVar(value=False)
        self.order_type_var = tk.StringVar(value="매장식사")
        self.spoon_var = tk.StringVar(value="수저필요함")

        self._build_ui()

    def _build_ui(self) -> None:
        # 1. 상단 헤더 영역
        header_frame = tk.Frame(self, bg="#E65100", height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title_lbl = tk.Label(
            header_frame,
            text=f"🍙  {STORE_NAME} 무인 주문 키오스크",
            font=("Malgun Gothic", 20, "bold"),
            fg="#FFFFFF",
            bg="#E65100",
        )
        title_lbl.pack(side=tk.LEFT, padx=25)

        badge_lbl = tk.Label(
            header_frame,
            text=f"단말기 ID: {STORE_ID}  |  보안연결: HTTPS + API Key",
            font=("Malgun Gothic", 10, "bold"),
            fg="#FFE0B2",
            bg="#E65100",
        )
        badge_lbl.pack(side=tk.RIGHT, padx=25)

        # 2. 메인 컨테이너
        main_frame = tk.Frame(self, bg="#FFF8E1", padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 좌측 영역 (김밥 전용 옵션 & 카테고리 탭) ---
        left_frame = tk.Frame(main_frame, bg="#FFFFFF", bd=1, relief=tk.SOLID)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 김밥 전용 기호 재료 제외 옵션 바
        veggie_bar = tk.Frame(left_frame, bg="#FFF3E0", padx=15, pady=12)
        veggie_bar.pack(fill=tk.X)

        tk.Label(
            veggie_bar,
            text="① 김밥류 기호 옵션 (메뉴 클릭 전 체크):",
            font=("Malgun Gothic", 11, "bold"),
            bg="#FFF3E0",
            fg="#BF360C",
        ).pack(side=tk.LEFT, padx=(0, 12))

        carrot_cb = tk.Checkbutton(
            veggie_bar,
            text="🥕 당근 제외",
            variable=self.no_carrot_var,
            font=("Malgun Gothic", 11, "bold"),
            fg="#D84315",
            bg="#FFF3E0",
            activebackground="#FFF3E0",
        )
        carrot_cb.pack(side=tk.LEFT, padx=8)

        cucumber_cb = tk.Checkbutton(
            veggie_bar,
            text="🥒 오이 제외",
            variable=self.no_cucumber_var,
            font=("Malgun Gothic", 11, "bold"),
            fg="#2E7D32",
            bg="#FFF3E0",
            activebackground="#FFF3E0",
        )
        cucumber_cb.pack(side=tk.LEFT, padx=8)

        # 카테고리 탭
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TNotebook.Tab",
            font=("Malgun Gothic", 12, "bold"),
            padding=[18, 8],
            background="#FFE0B2",
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#E65100")],
            foreground=[("selected", "#FFFFFF")],
        )

        notebook = ttk.Notebook(left_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        categories = ["김밥류", "식사/분식류"]
        for cat in categories:
            tab = tk.Frame(notebook, bg="#FFFFFF", padx=10, pady=10)
            notebook.add(tab, text=f"  {cat}  ")
            self._populate_menu_grid(tab, cat)

        # --- 우측 영역 (장바구니 및 결제) ---
        right_frame = tk.Frame(main_frame, bg="#FFFFFF", width=380, bd=1, relief=tk.SOLID)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)

        cart_header = tk.Frame(right_frame, bg="#E65100", pady=10, padx=12)
        cart_header.pack(fill=tk.X)
        tk.Label(
            cart_header,
            text="🛒 주문 장바구니",
            font=("Malgun Gothic", 13, "bold"),
            fg="#FFFFFF",
            bg="#E65100",
        ).pack(side=tk.LEFT)

        tk.Button(
            cart_header,
            text="전체 비우기",
            font=("Malgun Gothic", 9, "bold"),
            bg="#FF8A65",
            fg="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.clear_cart,
        ).pack(side=tk.RIGHT)

        # 장바구니 목록 (Treeview)
        tree_frame = tk.Frame(right_frame, bg="#FFFFFF", padx=10, pady=8)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("menu", "opt", "qty", "price")
        self.cart_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=10
        )
        self.cart_tree.heading("menu", text="메뉴명")
        self.cart_tree.heading("opt", text="기호옵션")
        self.cart_tree.heading("qty", text="수량")
        self.cart_tree.heading("price", text="금액")

        self.cart_tree.column("menu", width=110, anchor=tk.W)
        self.cart_tree.column("opt", width=110, anchor=tk.CENTER)
        self.cart_tree.column("qty", width=40, anchor=tk.CENTER)
        self.cart_tree.column("price", width=80, anchor=tk.E)
        self.cart_tree.pack(fill=tk.BOTH, expand=True)

        # 장바구니 수량 조절 / 삭제 버튼 바
        ctrl_frame = tk.Frame(right_frame, bg="#FFFFFF", padx=10, pady=4)
        ctrl_frame.pack(fill=tk.X)

        tk.Button(
            ctrl_frame,
            text="➕ 수량 증가",
            font=("Malgun Gothic", 10, "bold"),
            bg="#FFF3E0",
            relief=tk.GROOVE,
            command=lambda: self.change_qty(1),
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        tk.Button(
            ctrl_frame,
            text="➖ 수량 감소",
            font=("Malgun Gothic", 10, "bold"),
            bg="#FFF3E0",
            relief=tk.GROOVE,
            command=lambda: self.change_qty(-1),
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        tk.Button(
            ctrl_frame,
            text="🗑️ 선택 삭제",
            font=("Malgun Gothic", 10, "bold"),
            bg="#FFCDD2",
            fg="#B71C1C",
            relief=tk.GROOVE,
            command=self.remove_selected_item,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # 공통 옵션 선택 영역
        opt_frame = tk.LabelFrame(
            right_frame,
            text=" ② 매장 공통 옵션 선택 ",
            font=("Malgun Gothic", 11, "bold"),
            bg="#FAFAFA",
            fg="#BF360C",
            padx=12,
            pady=10,
        )
        opt_frame.pack(fill=tk.X, padx=10, pady=8)

        row1 = tk.Frame(opt_frame, bg="#FAFAFA")
        row1.pack(fill=tk.X, pady=3)
        tk.Label(
            row1, text="• 식사 형태:", font=("Malgun Gothic", 10, "bold"), bg="#FAFAFA"
        ).pack(side=tk.LEFT)
        tk.Radiobutton(
            row1,
            text="매장식사",
            variable=self.order_type_var,
            value="매장식사",
            font=("Malgun Gothic", 10),
            bg="#FAFAFA",
        ).pack(side=tk.LEFT, padx=8)
        tk.Radiobutton(
            row1,
            text="포장 (To-go)",
            variable=self.order_type_var,
            value="포장",
            font=("Malgun Gothic", 10),
            bg="#FAFAFA",
        ).pack(side=tk.LEFT, padx=8)

        row2 = tk.Frame(opt_frame, bg="#FAFAFA")
        row2.pack(fill=tk.X, pady=3)
        tk.Label(
            row2, text="• 수저/젓가락:", font=("Malgun Gothic", 10, "bold"), bg="#FAFAFA"
        ).pack(side=tk.LEFT)
        tk.Radiobutton(
            row2,
            text="수저필요함",
            variable=self.spoon_var,
            value="수저필요함",
            font=("Malgun Gothic", 10),
            bg="#FAFAFA",
        ).pack(side=tk.LEFT, padx=4)
        tk.Radiobutton(
            row2,
            text="수저필요없음",
            variable=self.spoon_var,
            value="수저필요없음",
            font=("Malgun Gothic", 10),
            bg="#FAFAFA",
        ).pack(side=tk.LEFT, padx=4)

        # 총 결제 금액 및 결제 버튼
        bottom_frame = tk.Frame(right_frame, bg="#FFF3E0", padx=12, pady=12)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.total_lbl = tk.Label(
            bottom_frame,
            text="총 결제 금액: 0원",
            font=("Malgun Gothic", 15, "bold"),
            fg="#BF360C",
            bg="#FFF3E0",
        )
        self.total_lbl.pack(fill=tk.X, pady=(0, 8))

        self.order_btn = tk.Button(
            bottom_frame,
            text="💳 결제 및 주문하기",
            font=("Malgun Gothic", 14, "bold"),
            bg="#E65100",
            fg="#FFFFFF",
            activebackground="#BF360C",
            activeforeground="#FFFFFF",
            height=2,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.submit_order_async,
        )
        self.order_btn.pack(fill=tk.X)

    def _populate_menu_grid(self, parent: tk.Frame, category: str) -> None:
        cat_menus = [m for m in self.menus if m["category"] == category]
        icon = "🍙" if category == "김밥류" else "🍜"
        for idx, menu in enumerate(cat_menus):
            r = idx // 3
            c = idx % 3
            card = tk.Button(
                parent,
                text=f"{icon}\n{menu['menu_name']}\n\n{menu['price']:,}원",
                font=("Malgun Gothic", 12, "bold"),
                bg="#FFFDE7",
                fg="#BF360C",
                activebackground="#FFE082",
                relief=tk.RAISED,
                bd=2,
                width=16,
                height=5,
                cursor="hand2",
                command=lambda m=menu: self.add_to_cart(m),
            )
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

        for i in range(3):
            parent.grid_columnconfigure(i, weight=1)

    def add_to_cart(self, menu: Dict[str, Any]) -> None:
        if menu["category"] == "김밥류":
            carrot_opt = "당근제외" if self.no_carrot_var.get() else "당근포함"
            cucumber_opt = "오이제외" if self.no_cucumber_var.get() else "오이포함"
            opt_label = f"{carrot_opt}/{cucumber_opt}"
        else:
            carrot_opt = "당근포함"
            cucumber_opt = "오이포함"
            opt_label = "기본조리"

        for item in self.cart:
            if (
                item["menu_name"] == menu["menu_name"]
                and item["exclude_carrot"] == carrot_opt
                and item["exclude_cucumber"] == cucumber_opt
            ):
                item["quantity"] += 1
                self._refresh_cart_ui()
                return

        self.cart.append(
            {
                "menu_name": menu["menu_name"],
                "price": int(menu["price"]),
                "quantity": 1,
                "exclude_carrot": carrot_opt,
                "exclude_cucumber": cucumber_opt,
                "opt_label": opt_label,
            }
        )
        self._refresh_cart_ui()

    def change_qty(self, delta: int) -> None:
        sel = self.cart_tree.selection()
        if not sel:
            return
        idx = self.cart_tree.index(sel[0])
        self.cart[idx]["quantity"] += delta
        if self.cart[idx]["quantity"] <= 0:
            del self.cart[idx]
        self._refresh_cart_ui()

    def remove_selected_item(self) -> None:
        sel = self.cart_tree.selection()
        if not sel:
            return
        idx = self.cart_tree.index(sel[0])
        del self.cart[idx]
        self._refresh_cart_ui()

    def clear_cart(self) -> None:
        self.cart.clear()
        self._refresh_cart_ui()

    def _refresh_cart_ui(self) -> None:
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        total = 0
        for item in self.cart:
            sub = item["price"] * item["quantity"]
            total += sub
            self.cart_tree.insert(
                "",
                tk.END,
                values=(
                    item["menu_name"],
                    item["opt_label"],
                    item["quantity"],
                    f"{sub:,}원",
                ),
            )
        self.total_lbl.config(text=f"총 결제 금액: {total:,}원")

    def submit_order_async(self) -> None:
        """결제 버튼 클릭 시 UI 프리징(렉) 방지를 위해 백그라운드 스레드에서 HTTPS 요청 수행"""
        if not self.cart:
            messagebox.showwarning("장바구니 비어있음", "주문할 메뉴를 먼저 선택해 주세요!")
            return

        payload = {
            "store_id": STORE_ID,
            "store_name": STORE_NAME,
            "order_type": self.order_type_var.get(),
            "spoon_needed": self.spoon_var.get(),
            "items": [
                {
                    "menu_name": item["menu_name"],
                    "price": item["price"],
                    "quantity": item["quantity"],
                    "temperature": None,
                    "exclude_carrot": item["exclude_carrot"],
                    "exclude_cucumber": item["exclude_cucumber"],
                }
                for item in self.cart
            ],
        }

        self.order_btn.config(state=tk.DISABLED, text="⏳ 결제 및 서버 전송 중...")
        worker = threading.Thread(
            target=self._send_order_worker, args=(payload,), daemon=True
        )
        worker.start()

    def _send_order_worker(self, payload: Dict[str, Any]) -> None:
        try:
            resp = requests.post(
                f"{BASE_URL}/order",
                json=payload,
                headers=DEFAULT_HEADERS,
                verify=False,
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.after(0, self._on_order_success, data)
            else:
                self.after(
                    0,
                    self._on_order_error,
                    f"서버 응답 오류 ({resp.status_code}): {resp.text}",
                )
        except requests.exceptions.ConnectionError:
            self.after(
                0,
                self._on_order_error,
                "중앙 서버(server.py)에 연결할 수 없습니다.\n먼저 python server.py를 실행해 주세요!",
            )
        except Exception as exc:
            self.after(0, self._on_order_error, f"통신 중 예외 발생: {exc}")

    def _on_order_success(self, data: Dict[str, Any]) -> None:
        self.order_btn.config(state=tk.NORMAL, text="💳 결제 및 주문하기")
        order_id = data.get("order_id", "?")
        total_price = data.get("total_price", 0)
        messagebox.showinfo(
            "주문 완료",
            f"🍙 [{STORE_NAME}] 주문이 정상 접수되었습니다!\n\n"
            f"• 주문 번호: #{order_id}번\n"
            f"• 식사 형태: {self.order_type_var.get()} ({self.spoon_var.get()})\n"
            f"• 결제 금액: {total_price:,}원\n\n"
            f"가상 모바일 폰 화면에서 조리 시작 및 픽업 알림을 확인하세요!",
        )
        self.clear_cart()

    def _on_order_error(self, err_msg: str) -> None:
        self.order_btn.config(state=tk.NORMAL, text="💳 결제 및 주문하기")
        messagebox.showerror("주문 전송 실패", err_msg)


if __name__ == "__main__":
    app = GimbapKiosk()
    app.mainloop()

