"""
[KDS 주방 주문 현황판 클라이언트 - kitchen_client.py]
- UI 프레임워크: Python 표준 Tkinter (라이트 화이트 테마)
- 핵심 기능:
  1) 시인성 높은 주문 카드: 주문 번호(#), 매장명, 포장/매장 구분, 주문 시각
  2) 상세 메뉴 및 옵션: 메뉴명, 수량, ICE/HOT 및 당근/오이 제외 옵션 태그
  3) 2단계 상태 변경 버튼:
     - [ 준비중 ⏳ ] (주황색) ➔ 클릭 시 ➔ [ 조리 완료 ✔ ] (초록색)
     - [ 조리 완료 ✔ ] ➔ 한 번 더 클릭 시 ➔ 화면에서 삭제
  4) 우측 상단 조리 완료 기록:
     - 최근 완료 주문 번호 칩(Chip) 목록 실시간 표시
     - [📋 완료 기록] 클릭 시 전체 완료 주문 내역 팝업 조회
     - SQLite DB 연동으로 이전 완료 주문 기록 자동 로드
  5) 반응형 바둑판(Grid) 자동 정렬
- 실시간 통신: WebSocket(wss://.../ws/kitchen) 실시간 수신 + 1.5초 주기 REST 폴링 백업
- 스레드 안전성: root.after() 메시지 큐 위임 방식으로 UI 갱신 충돌 방지
"""

import asyncio
import json
import ssl
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Set, Tuple
import urllib.error
import urllib.request

try:
    import urllib3
    import requests
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    requests = None

try:
    import websockets
except ImportError:
    websockets = None

from config import (
    BASE_URL,
    DEFAULT_HEADERS,
    POLLING_INTERVAL_SEC,
    SHARED_API_KEY,
    WS_KITCHEN_ENDPOINT,
)


class KitchenDisplaySystem(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("👨‍🍳 KDS 주방 주문 현황판 (Kitchen Display System)")
        self.geometry("1180x820")
        self.minsize(780, 560)
        self.configure(bg="#FFFFFF")

        # 활성 주문 관리: {order_id: {"status": "PREPARING" | "COMPLETED", "card": Frame, ...}}
        self.orders: Dict[int, Dict[str, Any]] = {}
        # 화면에서 삭제(dismiss)된 주문 ID 목록 (재추가 방지)
        self.dismissed_ids: Set[int] = set()

        # 조리 완료 주문 기록 리스트: [{"order_id": int, "store_name": str, ...}]
        self.completed_history: List[Dict[str, Any]] = []

        # 스레드 종료 제어 플래그
        self.is_running = True

        self._build_ui()

        # DB에서 기존 조리 완료된 주문 기록 자동 로드
        self._load_initial_completed_history()

        # WebSocket 실시간 수신 데몬 스레드 시작 (websockets 설치 시)
        if websockets is not None:
            self.ws_thread = threading.Thread(target=self._websocket_worker, daemon=True)
            self.ws_thread.start()

        # 백그라운드 폴링 데몬 스레드 시작 (1.5초 주기 백업 동기화)
        self.poll_thread = threading.Thread(target=self._polling_worker, daemon=True)
        self.poll_thread.start()

        # 창 종료 이벤트 바인딩
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        # ========================================================
        # 1. 상단 화이트 헤더 바
        # ========================================================
        header = tk.Frame(self, bg="#FFFFFF", height=82, padx=20, pady=10)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # 헤더 하단 구분선
        header_divider = tk.Frame(self, bg="#E2E8F0", height=1)
        header_divider.pack(fill=tk.X)

        # [좌측] 메인 타이틀 & 안내 문구
        left_box = tk.Frame(header, bg="#FFFFFF")
        left_box.pack(side=tk.LEFT, fill=tk.Y)

        title_lbl = tk.Label(
            left_box,
            text="👨‍🍳 KDS 주방 주문 현황판",
            font=("Malgun Gothic", 18, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
        )
        title_lbl.pack(anchor=tk.W)

        sub_lbl = tk.Label(
            left_box,
            text="[준비중 ⏳] 누르면 조리완료 ➔ [조리 완료 ✔] 누르면 화면에서 삭제",
            font=("Malgun Gothic", 9),
            fg="#64748B",
            bg="#FFFFFF",
        )
        sub_lbl.pack(anchor=tk.W, pady=(2, 0))

        # [우측] 상태 뱃지 & 실시간 조리 완료 기록
        right_box = tk.Frame(header, bg="#FFFFFF")
        right_box.pack(side=tk.RIGHT, fill=tk.Y)

        # 1층: 서버 연결 상태 & 카운트 뱃지 & 완료 기록 버튼
        row1 = tk.Frame(right_box, bg="#FFFFFF")
        row1.pack(anchor=tk.E, pady=(0, 5))

        self.conn_lbl = tk.Label(
            row1,
            text="○ 서버 연결 대기",
            font=("Malgun Gothic", 9, "bold"),
            fg="#DC2626",
            bg="#FFFFFF",
        )
        self.conn_lbl.pack(side=tk.LEFT, padx=(0, 8))

        self.prep_count_lbl = tk.Label(
            row1,
            text="준비중: 0",
            font=("Malgun Gothic", 9, "bold"),
            fg="#FFFFFF",
            bg="#EA580C",
            padx=8,
            pady=2,
        )
        self.prep_count_lbl.pack(side=tk.LEFT, padx=3)

        self.ready_count_lbl = tk.Label(
            row1,
            text="조리완료: 0",
            font=("Malgun Gothic", 9, "bold"),
            fg="#FFFFFF",
            bg="#16A34A",
            padx=8,
            pady=2,
        )
        self.ready_count_lbl.pack(side=tk.LEFT, padx=3)

        # 완료 기록 상세 팝업 버튼
        self.history_btn = tk.Button(
            row1,
            text="📋 완료 기록 (0건)",
            font=("Malgun Gothic", 9, "bold"),
            fg="#FFFFFF",
            bg="#2563EB",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            padx=8,
            pady=2,
            command=self._show_completed_history_dialog,
        )
        self.history_btn.pack(side=tk.LEFT, padx=(6, 0))

        # 2층: 최근 완료 주문 번호 칩(Chips) 목록
        row2 = tk.Frame(right_box, bg="#FFFFFF")
        row2.pack(anchor=tk.E)

        tk.Label(
            row2,
            text="최근 완료 기록 ➔",
            font=("Malgun Gothic", 9, "bold"),
            fg="#64748B",
            bg="#FFFFFF",
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.recent_chips_frame = tk.Frame(row2, bg="#FFFFFF")
        self.recent_chips_frame.pack(side=tk.LEFT)

        self.empty_history_lbl = tk.Label(
            self.recent_chips_frame,
            text="(완료된 주문 없음)",
            font=("Malgun Gothic", 9),
            fg="#64748B",
            bg="#FFFFFF",
        )
        self.empty_history_lbl.pack(side=tk.LEFT)

        # ========================================================
        # 2. 메인 스크롤 가능 바둑판(Grid) 컨테이너
        # ========================================================
        self.canvas_frame = tk.Frame(self, bg="#FFFFFF")
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        self.canvas = tk.Canvas(
            self.canvas_frame,
            bg="#FFFFFF",
            highlightthickness=0,
            bd=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self.canvas_frame,
            orient=tk.VERTICAL,
            command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 카드들이 바둑판 모양으로 올라갈 내부 프레임
        self.grid_container = tk.Frame(self.canvas, bg="#FFFFFF")
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.grid_container, anchor="nw"
        )

        self.grid_container.bind("<Configure>", self._on_container_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 대기 주문 없을 때 안내 문구
        self.empty_label = tk.Label(
            self.canvas,
            text="🔔 접수된 주문이 없습니다.\n새 주문이 들어오면 현황판에 카드가 자동으로 생성됩니다.",
            font=("Malgun Gothic", 16, "bold"),
            fg="#64748B",
            bg="#FFFFFF",
            justify=tk.CENTER,
        )
        self.empty_label.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

    # -------------------------------------------------------------
    # DB에서 과거 완료된 주문 로드 (앱 재시작 시 복원)
    # -------------------------------------------------------------
    def _load_initial_completed_history(self) -> None:
        try:
            from database import get_db_connection

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT o.order_id, s.store_name, o.order_type, o.order_time
                FROM orders o
                JOIN stores s ON o.store_id = s.store_id
                WHERE o.status = 'COMPLETED'
                ORDER BY o.order_id DESC LIMIT 20;
                """
            )
            rows = cursor.fetchall()
            for r in reversed(rows):
                cursor.execute(
                    """
                    SELECT m.menu_name, oi.quantity, oi.temperature
                    FROM order_items oi
                    JOIN menus m ON oi.menu_id = m.menu_id
                    WHERE oi.order_id = ?;
                    """,
                    (r["order_id"],),
                )
                items = cursor.fetchall()
                items_desc = ", ".join(f"{it['menu_name']} x{it['quantity']}" for it in items)
                t_str = str(r["order_time"])
                comp_time = t_str.split()[-1] if " " in t_str else t_str

                self.completed_history.append(
                    {
                        "order_id": r["order_id"],
                        "store_name": r["store_name"],
                        "order_type": r["order_type"],
                        "items_desc": items_desc,
                        "completed_time": comp_time,
                    }
                )
                self.dismissed_ids.add(r["order_id"])

            conn.close()
            self._update_history_ui()
        except Exception as e:
            print(f"[KDS] 기존 완료 주문 로드 실패: {e}")

    # -------------------------------------------------------------
    # 캔버스 / 스크롤 제어
    # -------------------------------------------------------------
    def _on_container_configure(self, event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        self._regrid_cards()

    def _on_mousewheel(self, event) -> None:
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # -------------------------------------------------------------
    # 카드 바둑판(Grid) 자동 재배치
    # -------------------------------------------------------------
    def _regrid_cards(self) -> None:
        order_ids = list(self.orders.keys())
        if not order_ids:
            self.empty_label.place(relx=0.5, rely=0.45, anchor=tk.CENTER)
            return
        else:
            self.empty_label.place_forget()

        canvas_width = self.canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 1000

        card_width = 265
        num_cols = max(1, canvas_width // card_width)

        for idx, oid in enumerate(order_ids):
            row = idx // num_cols
            col = idx % num_cols
            card = self.orders[oid]["card"]
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

        for c in range(num_cols):
            self.grid_container.columnconfigure(c, weight=1)

    # -------------------------------------------------------------
    # 신규 주문 카드 생성 (주문 번호 + 상세 메뉴 + 2단계 버튼)
    # -------------------------------------------------------------
    def _add_order_card(self, ord_info: Dict[str, Any]) -> None:
        order_id = ord_info["order_id"]
        if order_id in self.orders or order_id in self.dismissed_ids:
            return

        store_name = ord_info.get("store_name", "")
        order_type = ord_info.get("order_type", "포장")
        items: List[Dict[str, Any]] = ord_info.get("items", [])
        order_time_raw = ord_info.get("order_time") or time.strftime("%H:%M:%S")
        order_time_str = order_time_raw.split()[-1] if " " in str(order_time_raw) else str(order_time_raw)

        # 1. 개별 주문 카드 외곽 프레임 (라이트 화이트 카드)
        card = tk.Frame(
            self.grid_container,
            bg="#FFFFFF",
            bd=2,
            relief=tk.FLAT,
            highlightthickness=2,
            highlightbackground="#CBD5E1",
            padx=14,
            pady=12,
        )

        # 2. 카드 상단 헤더: 큰 번호 + 매장명/포장 뱃지
        top_frame = tk.Frame(card, bg="#FFFFFF")
        top_frame.pack(fill=tk.X, pady=(0, 6))

        num_lbl = tk.Label(
            top_frame,
            text=f"#{order_id}",
            font=("Malgun Gothic", 28, "bold"),
            fg="#0F172A",
            bg="#FFFFFF",
        )
        num_lbl.pack(side=tk.LEFT)

        meta_box = tk.Frame(top_frame, bg="#FFFFFF")
        meta_box.pack(side=tk.RIGHT, anchor=tk.E)

        tk.Label(
            meta_box,
            text=store_name,
            font=("Malgun Gothic", 9, "bold"),
            fg="#475569",
            bg="#FFFFFF",
        ).pack(anchor=tk.E)

        type_bg = "#3B82F6" if order_type == "매장식사" else "#8B5CF6"
        tk.Label(
            meta_box,
            text=f"{order_type} ({order_time_str})",
            font=("Malgun Gothic", 8, "bold"),
            fg="#FFFFFF",
            bg=type_bg,
            padx=6,
            pady=1,
        ).pack(anchor=tk.E, pady=(2, 0))

        # 구분선
        sep = tk.Frame(card, bg="#E2E8F0", height=1)
        sep.pack(fill=tk.X, pady=(4, 8))

        # 3. 중앙 상세 메뉴 목록
        items_frame = tk.Frame(card, bg="#F8FAFC", padx=8, pady=8)
        items_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        if not items:
            tk.Label(
                items_frame,
                text="주문 내역 없음",
                font=("Malgun Gothic", 10),
                fg="#64748B",
                bg="#F8FAFC",
            ).pack(anchor=tk.W)
        else:
            for it in items:
                item_row = tk.Frame(items_frame, bg="#F8FAFC")
                item_row.pack(fill=tk.X, pady=2)

                menu_txt = f"• {it.get('menu_name', '')} x {it.get('quantity', 1)}"
                tk.Label(
                    item_row,
                    text=menu_txt,
                    font=("Malgun Gothic", 11, "bold"),
                    fg="#1E293B",
                    bg="#F8FAFC",
                ).pack(side=tk.LEFT)

                opt_parts = []
                temp = it.get("temperature")
                if temp:
                    opt_parts.append(temp)
                if it.get("exclude_carrot") == "당근제외":
                    opt_parts.append("당근X")
                if it.get("exclude_cucumber") == "오이제외":
                    opt_parts.append("오이X")

                if opt_parts:
                    opt_txt = f"[{', '.join(opt_parts)}]"
                    opt_fg = "#0284C7" if "ICE" in opt_parts else ("#DC2626" if "HOT" in opt_parts else "#D97706")
                    tk.Label(
                        item_row,
                        text=opt_txt,
                        font=("Malgun Gothic", 9, "bold"),
                        fg=opt_fg,
                        bg="#F8FAFC",
                    ).pack(side=tk.RIGHT)

        # 4. 하단 2단계 상태 변경 버튼
        btn = tk.Button(
            card,
            text="준비중 ⏳",
            font=("Malgun Gothic", 12, "bold"),
            bg="#EA580C",
            fg="#FFFFFF",
            activebackground="#C2410C",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            pady=7,
            command=lambda oid=order_id: self._handle_button_click(oid),
        )
        btn.pack(fill=tk.X, side=tk.BOTTOM)

        # 주문 데이터 보관
        self.orders[order_id] = {
            "status": "PREPARING",
            "card": card,
            "num_lbl": num_lbl,
            "btn": btn,
            "ord_info": ord_info,
        }

        self._regrid_cards()
        self._update_badges()

    # -------------------------------------------------------------
    # 2단계 상태 버튼 클릭 핸들러
    # -------------------------------------------------------------
    def _handle_button_click(self, order_id: int) -> None:
        if order_id not in self.orders:
            return

        info = self.orders[order_id]
        current_status = info["status"]

        if current_status == "PREPARING":
            # 1단계 -> 2단계: [조리 완료 ✔]로 변경
            info["status"] = "COMPLETED"
            info["btn"].configure(
                text="조리 완료 ✔",
                bg="#16A34A",
                activebackground="#15803D",
            )
            info["num_lbl"].configure(fg="#16A34A")
            info["card"].configure(highlightbackground="#16A34A")

            # 우측 상단 완료 주문 기록에 즉시 추가
            ord_data = info.get("ord_info", {})
            items = ord_data.get("items", [])
            items_desc = ", ".join(f"{it.get('menu_name')} x{it.get('quantity', 1)}" for it in items)
            record = {
                "order_id": order_id,
                "store_name": ord_data.get("store_name", ""),
                "order_type": ord_data.get("order_type", ""),
                "items_desc": items_desc,
                "completed_time": time.strftime("%H:%M:%S"),
            }
            if not any(r["order_id"] == order_id for r in self.completed_history):
                self.completed_history.append(record)
                self._update_history_ui()

            # 서버에 조리 완료 PATCH 전송 (고객 모바일 픽업 알림 생성)
            threading.Thread(
                target=self._send_complete_status,
                args=(order_id,),
                daemon=True,
            ).start()

            self._update_badges()

        elif current_status == "COMPLETED":
            # 2단계 -> 화면에서 완전히 삭제!
            self.dismissed_ids.add(order_id)
            info["card"].destroy()
            del self.orders[order_id]

            self._regrid_cards()
            self._update_badges()

    # -------------------------------------------------------------
    # 우측 상단 조리 완료 기록 UI 갱신
    # -------------------------------------------------------------
    def _update_history_ui(self) -> None:
        count = len(self.completed_history)
        self.history_btn.configure(text=f"📋 완료 기록 ({count}건)")

        for widget in self.recent_chips_frame.winfo_children():
            widget.destroy()

        if not self.completed_history:
            tk.Label(
                self.recent_chips_frame,
                text="(완료된 주문 없음)",
                font=("Malgun Gothic", 9),
                fg="#64748B",
                bg="#FFFFFF",
            ).pack(side=tk.LEFT)
            return

        # 최근 완료 주문 최대 5개 칩 표시
        recent = self.completed_history[-5:]
        for rec in recent:
            oid = rec["order_id"]
            chip = tk.Button(
                self.recent_chips_frame,
                text=f"#{oid} ✔",
                font=("Malgun Gothic", 9, "bold"),
                fg="#FFFFFF",
                bg="#059669",
                activebackground="#047857",
                activeforeground="#FFFFFF",
                relief=tk.FLAT,
                bd=0,
                padx=6,
                pady=1,
                cursor="hand2",
                command=lambda r=rec: self._show_order_detail_popup(r),
            )
            chip.pack(side=tk.LEFT, padx=2)

    def _show_order_detail_popup(self, rec: Dict[str, Any]) -> None:
        messagebox.showinfo(
            f"주문 #{rec['order_id']} 완료 상세",
            f"• 주문 번호: #{rec['order_id']}\n"
            f"• 매장: {rec['store_name']} ({rec['order_type']})\n"
            f"• 메뉴: {rec['items_desc']}\n"
            f"• 조리 완료 시각: {rec['completed_time']}",
            parent=self,
        )

    def _show_completed_history_dialog(self) -> None:
        """[📋 완료 기록] 전체 목록 팝업 다이얼로그"""
        dialog = tk.Toplevel(self)
        dialog.title(f"📜 조리 완료 주문 기록 (총 {len(self.completed_history)}건)")
        dialog.geometry("520x460")
        dialog.configure(bg="#FFFFFF")
        dialog.transient(self)

        # 팝업 헤더
        header = tk.Frame(dialog, bg="#F8FAFC", padx=16, pady=12)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="📜 조리 완료 및 픽업 호출 기록",
            font=("Malgun Gothic", 14, "bold"),
            fg="#0F172A",
            bg="#F8FAFC",
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"총 {len(self.completed_history)}건",
            font=("Malgun Gothic", 11, "bold"),
            fg="#059669",
            bg="#F8FAFC",
        ).pack(side=tk.RIGHT)

        tk.Frame(dialog, bg="#E2E8F0", height=1).pack(fill=tk.X)

        # 리스트 영역
        container = tk.Frame(dialog, bg="#FFFFFF", padx=12, pady=10)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, bg="#FFFFFF", highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)

        list_frame = tk.Frame(canvas, bg="#FFFFFF")
        win = canvas.create_window((0, 0), window=list_frame, anchor="nw")

        def _conf_list(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win, width=canvas.winfo_width())

        list_frame.bind("<Configure>", _conf_list)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        if not self.completed_history:
            tk.Label(
                list_frame,
                text="아직 조리 완료된 주문이 없습니다.",
                font=("Malgun Gothic", 12),
                fg="#64748B",
                bg="#FFFFFF",
                pady=30,
            ).pack(anchor=tk.CENTER)
        else:
            for rec in reversed(self.completed_history):
                card = tk.Frame(
                    list_frame,
                    bg="#F8FAFC",
                    bd=1,
                    relief=tk.SOLID,
                    highlightthickness=1,
                    highlightbackground="#CBD5E1",
                    padx=12,
                    pady=10,
                )
                card.pack(fill=tk.X, pady=4)

                top = tk.Frame(card, bg="#F8FAFC")
                top.pack(fill=tk.X)
                tk.Label(
                    top,
                    text=f"주문 #{rec['order_id']}",
                    font=("Malgun Gothic", 13, "bold"),
                    fg="#0284C7",
                    bg="#F8FAFC",
                ).pack(side=tk.LEFT)
                tk.Label(
                    top,
                    text=f"{rec['store_name']} ({rec['order_type']})  |  완료: {rec['completed_time']}",
                    font=("Malgun Gothic", 9),
                    fg="#475569",
                    bg="#F8FAFC",
                ).pack(side=tk.RIGHT)

                tk.Label(
                    card,
                    text=rec["items_desc"],
                    font=("Malgun Gothic", 10, "bold"),
                    fg="#0F172A",
                    bg="#F8FAFC",
                    anchor=tk.W,
                    justify=tk.LEFT,
                    pady=3,
                ).pack(fill=tk.X)

        btn_frame = tk.Frame(dialog, bg="#FFFFFF", pady=10)
        btn_frame.pack(fill=tk.X)
        tk.Button(
            btn_frame,
            text="닫기",
            font=("Malgun Gothic", 10, "bold"),
            fg="#0F172A",
            bg="#E2E8F0",
            activebackground="#CBD5E1",
            relief=tk.FLAT,
            padx=20,
            pady=5,
            command=dialog.destroy,
        ).pack(anchor=tk.CENTER)

    # -------------------------------------------------------------
    # 상단 뱃지 카운트 갱신
    # -------------------------------------------------------------
    def _update_badges(self) -> None:
        prep_count = sum(1 for o in self.orders.values() if o["status"] == "PREPARING")
        ready_count = sum(1 for o in self.orders.values() if o["status"] == "COMPLETED")

        self.prep_count_lbl.configure(text=f"준비중: {prep_count}")
        self.ready_count_lbl.configure(text=f"조리완료: {ready_count}")

    # -------------------------------------------------------------
    # 서버 API 비동기 통신 (requests 미설치 시 urllib.request 폴백)
    # -------------------------------------------------------------
    def _http_request(self, method: str, url: str) -> Tuple[int, Any]:
        """requests 우선 사용, 미설치 환경에서는 표준 라이브러리 urllib.request로 폴백합니다."""
        if requests is not None:
            resp = requests.request(
                method,
                url,
                headers=DEFAULT_HEADERS,
                verify=False,
                timeout=3,
            )
            data = resp.json() if resp.status_code == 200 and resp.content else None
            return resp.status_code, data

        ssl_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS, method=method)
        try:
            with urllib.request.urlopen(req, context=ssl_ctx, timeout=3) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw) if raw else None
                return resp.status, data
        except urllib.error.HTTPError as err:
            return err.code, None

    def _send_accept_status(self, order_id: int) -> None:
        try:
            url = f"{BASE_URL}/orders/{order_id}/accept"
            self._http_request("PATCH", url)
        except Exception as e:
            print(f"[KDS] 주문 #{order_id} 접수 통신 실패: {e}")

    def _send_complete_status(self, order_id: int) -> None:
        try:
            url = f"{BASE_URL}/orders/{order_id}/complete"
            self._http_request("PATCH", url)
        except Exception as e:
            print(f"[KDS] 주문 #{order_id} 조리완료 통신 실패: {e}")

    # -------------------------------------------------------------
    # WebSocket 실시간 수신 데몬 스레드
    # -------------------------------------------------------------
    def _websocket_worker(self) -> None:
        if websockets is None:
            return
        asyncio.run(self._ws_loop())

    async def _ws_loop(self) -> None:
        if websockets is None:
            return
        ws_url = f"{WS_KITCHEN_ENDPOINT}?token={SHARED_API_KEY}"
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        while self.is_running:
            try:
                async with websockets.connect(ws_url, ssl=ssl_context) as ws:
                    if self.is_running:
                        self.after(0, self._set_connection_status, True)
                    while self.is_running:
                        try:
                            raw_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue

                        msg = json.loads(raw_msg)
                        event = msg.get("event")
                        if event == "INIT_ORDERS":
                            self.after(0, self._process_polled_orders, msg.get("orders", []))
                        elif event == "NEW_ORDER":
                            self.after(
                                0,
                                self._process_polled_orders,
                                [{**msg, "status": "PENDING"}],
                            )
            except Exception:
                if self.is_running:
                    self.after(0, self._set_connection_status, False)
                    await asyncio.sleep(2.0)

    # -------------------------------------------------------------
    # 백그라운드 폴링 데몬 스레드 (1.5초 주기 백업)
    # -------------------------------------------------------------
    def _polling_worker(self) -> None:
        url = f"{BASE_URL}/orders/kitchen"
        while self.is_running:
            try:
                status_code, order_list = self._http_request("GET", url)
                if status_code == 200 and order_list is not None:
                    self.after(0, self._process_polled_orders, order_list)
                    self.after(0, self._set_connection_status, True)
                else:
                    self.after(0, self._set_connection_status, False)
            except Exception:
                self.after(0, self._set_connection_status, False)

            time.sleep(POLLING_INTERVAL_SEC)

    def _set_connection_status(self, is_ok: bool) -> None:
        if not self.is_running:
            return
        if is_ok:
            self.conn_lbl.configure(text="● 서버 연결됨", fg="#059669")
        else:
            self.conn_lbl.configure(text="○ 서버 연결 대기", fg="#DC2626")

    def _process_polled_orders(self, order_list: list) -> None:
        for ord_info in order_list:
            oid = ord_info["order_id"]
            if oid in self.dismissed_ids:
                continue

            if oid not in self.orders:
                if ord_info.get("status") == "PENDING":
                    threading.Thread(
                        target=self._send_accept_status,
                        args=(oid,),
                        daemon=True,
                    ).start()

                self._add_order_card(ord_info)

    def _on_close(self) -> None:
        self.is_running = False
        self.destroy()


if __name__ == "__main__":
    app = KitchenDisplaySystem()
    app.mainloop()

