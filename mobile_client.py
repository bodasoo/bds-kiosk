"""
[3주차 L4 TCP 소켓 개편] 가상 모바일 폰 고객용 실시간 푸시 알림 클라이언트 (mobile_client.py)
- 외부 패키지(HTTP, WebSocket 등) 없이 Python 표준 라이브러리(socket, threading, queue, tkinter)만 사용합니다.
- 스마트폰 UI 디자인: 세로형(360x700), 스마트폰 상단 상태 바(실시간 시계, 5G, 배터리),
  스크롤 가능한 실시간 알림 피드, 알림 모두 지우기, 서버 연결 상태 표시등.
- 실시간 통신: L4 TCP 소켓 지속 연결 + 백그라운드 수신 스레드(Daemon) -> queue.Queue -> root.after() GUI 큐 파이프라인.
- 무(無)폴링 실시간 Push: 주방에서 상태 변경(COOKING/COMPLETED) 시 서버가 밀어 넣은 푸시 패킷을 즉시 수신하여 렌더링.
"""

from datetime import datetime
import json
import queue
import socket
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from typing import Any, Dict, List, Optional

from config import (
    RECONNECT_INTERVAL,
    SERVER_HOST,
    SERVER_PORT,
    SHARED_API_KEY,
)
from socket_utils import (
    ACTION_NOTIFICATION_PUSH,
    ACTION_ORDER_STATUS_BROADCAST,
    ACTION_REGISTER,
    ROLE_MOBILE,
    make_request,
    recv_packet,
    send_packet,
)


class VirtualMobileClient(tk.Tk):
    """가상 스마트폰 고객용 실시간 푸시 알림 클라이언트."""

    def __init__(self) -> None:
        super().__init__()

        # 1. 윈도우 기본 사양 (360x700 세로형 스마트폰 비율 고정)
        self.title("BDS Mobile - 주문 푸시 알림")
        self.geometry("360x700")
        self.resizable(False, False)
        self.configure(bg="#0F172A")  # 외곽 폰 베젤 다크 슬레이트

        # 2. 상태 관리 변수
        self.is_running = True
        self._sock: Optional[socket.socket] = None
        self.gui_queue: queue.Queue[tuple] = queue.Queue()
        self.notifications: List[Dict[str, Any]] = []

        # 폰트 캐시
        self._init_fonts()

        # 3. UI 컴포넌트 빌드
        self._build_ui()

        # 4. 상단 상태 바 시계 주기적 업데이트
        self._update_clock()

        # 5. 메인 GUI 큐 폴링 시작 (100ms 주기)
        self.after(100, self._poll_gui_queue)

        # 6. 순수 TCP 백그라운드 수신 스레드 시작
        self.rx_thread = threading.Thread(
            target=self._tcp_receiver_worker,
            name="Mobile-TCP-Receiver",
            daemon=True,
        )
        self.rx_thread.start()

        # 7. 창 종료 이벤트
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_fonts(self) -> None:
        """스마트폰 UI용 서체 정의."""
        self.font_time = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.font_status = tkfont.Font(family="Segoe UI", size=8)
        self.font_app_title = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.font_app_sub = tkfont.Font(family="Segoe UI", size=8)
        self.font_card_store = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.font_card_badge = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        self.font_card_summary = tkfont.Font(family="Segoe UI", size=9)
        self.font_card_msg = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.font_card_time = tkfont.Font(family="Segoe UI", size=7)
        self.font_btn = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.font_conn = tkfont.Font(family="Segoe UI", size=8, weight="bold")

    # -------------------------------------------------------------------------
    # UI 빌드 (스마트폰 베젤, 상단 상태바, 헤더, 피드, 하단 컨트롤바)
    # -------------------------------------------------------------------------
    def _build_ui(self) -> None:
        # 스마트폰 본체 래퍼
        self.phone_wrapper = tk.Frame(self, bg="#0F172A", bd=0)
        self.phone_wrapper.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 스마트폰 내부 스크린 (라이트 그레이 배경)
        self.screen_frame = tk.Frame(self.phone_wrapper, bg="#F1F5F9", bd=0)
        self.screen_frame.pack(fill=tk.BOTH, expand=True)

        # -----------------------------
        # 1) 최상단 스마트폰 상태 바 (Status Bar)
        # -----------------------------
        self.status_bar = tk.Frame(self.screen_frame, bg="#0F172A", height=24)
        self.status_bar.pack(fill=tk.X, side=tk.TOP)
        self.status_bar.pack_propagate(False)

        # 좌측: 실시간 시계
        self.clock_lbl = tk.Label(
            self.status_bar,
            text="12:00",
            bg="#0F172A",
            fg="#F8FAFC",
            font=self.font_time,
            padx=10,
        )
        self.clock_lbl.pack(side=tk.LEFT)

        # 중앙: 다이내믹 아일랜드 / 카메라 노치
        notch = tk.Label(
            self.status_bar,
            text="●",
            bg="#0F172A",
            fg="#334155",
            font=("Segoe UI", 8),
        )
        notch.pack(side=tk.LEFT, expand=True)

        # -----------------------------
        # 2) 앱 헤더 (App Header)
        # -----------------------------
        self.header_frame = tk.Frame(self.screen_frame, bg="#1E293B", height=46)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)
        self.header_frame.pack_propagate(False)

        title_container = tk.Frame(self.header_frame, bg="#1E293B")
        title_container.pack(side=tk.LEFT, padx=14, pady=10)

        app_title = tk.Label(
            title_container,
            text="알림창",
            bg="#1E293B",
            fg="#FFFFFF",
            font=self.font_app_title,
        )
        app_title.pack(anchor="w")

        # -----------------------------
        # 3) 중앙: 스크롤 가능한 알림 피드
        # -----------------------------
        self.feed_container = tk.Frame(self.screen_frame, bg="#F1F5F9")
        self.feed_container.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        self.canvas = tk.Canvas(self.feed_container, bg="#F1F5F9", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(
            self.feed_container,
            orient="vertical",
            command=self.canvas.yview,
            width=8,
        )
        self.scrollable_frame = tk.Frame(self.canvas, bg="#F1F5F9")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw",
            width=344,
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 캔버스 너비 반응형 바인딩 및 마우스 휠 지원
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width),
        )
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 초기 빈 피드 화면 렌더링
        self._render_empty_feed()

        # -----------------------------
        # 4) 하단 컨트롤 바 (Buttons)
        # -----------------------------
        self.bottom_bar = tk.Frame(
            self.screen_frame,
            bg="#FFFFFF",
            height=58,
            highlightthickness=1,
            highlightbackground="#E2E8F0",
        )
        self.bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.bottom_bar.pack_propagate(False)

        # 우측: [알림 모두 지우기] 버튼
        self.clear_btn = tk.Button(
            self.bottom_bar,
            text="모두 지우기",
            command=self._clear_all_notifications,
            bg="#F1F5F9",
            fg="#475569",
            activebackground="#E2E8F0",
            activeforeground="#0F172A",
            font=self.font_btn,
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.clear_btn.pack(side=tk.RIGHT, padx=12, pady=10)

    def _on_mousewheel(self, event: tk.Event) -> None:
        """마우스 휠 스크롤 지원."""
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _update_clock(self) -> None:
        """상단 상태 바 시계 매초 갱신."""
        if not self.is_running:
            return
        now_str = datetime.now().strftime("%H:%M")
        self.clock_lbl.configure(text=now_str)
        self.after(1000, self._update_clock)

    # -------------------------------------------------------------------------
    # 알림 피드 렌더링 & 카드 생성
    # -------------------------------------------------------------------------
    def _render_empty_feed(self) -> None:
        """수신된 알림이 없을 때 표시되는 빈 화면."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        self.empty_frame = tk.Frame(self.scrollable_frame, bg="#F1F5F9", pady=120)
        self.empty_frame.pack(fill=tk.BOTH, expand=True)

        empty_icon = tk.Label(
            self.empty_frame,
            text="🔔",
            font=("Segoe UI", 36),
            bg="#F1F5F9",
            fg="#94A3B8",
        )
        empty_icon.pack()

        empty_title = tk.Label(
            self.empty_frame,
            text="수신된 알림이 없습니다",
            font=self.font_card_msg,
            bg="#F1F5F9",
            fg="#64748B",
            pady=4,
        )
        empty_title.pack()

        empty_desc = tk.Label(
            self.empty_frame,
            text="주문이 접수되거나 조리가 완료되면\n실시간으로 푸시 알림이 도착합니다.",
            font=self.font_app_sub,
            bg="#F1F5F9",
            fg="#94A3B8",
            justify="center",
        )
        empty_desc.pack()

    def _clear_all_notifications(self) -> None:
        """알림 모두 지우기 동작."""
        self.notifications.clear()
        self._render_empty_feed()

    def _add_notification_card(self, data: Dict[str, Any]) -> None:
        """새로운 알림 푸시 패킷을 파싱하여 피드 최상단에 카드로 추가합니다."""
        # 최초 1건 추가 시 빈 화면 제거
        if len(self.notifications) == 0 and hasattr(self, "empty_frame"):
            self.empty_frame.destroy()

        self.notifications.insert(0, data)

        order_id = data.get("order_id", "-")
        store_name = data.get("store_name", "보다수 매장")
        status = str(data.get("status", "COOKING")).upper()
        summary_text = data.get("summary_text") or "주문 메뉴"
        message = data.get("message") or "상태가 변경되었습니다."
        timestamp = data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 상태별 배지 색상 및 텍스트 결정
        if status == "COOKING":
            badge_text = "🔥 조리 시작"
            badge_bg = "#FEF3C7"  # 은은한 앰버 옐로우
            badge_fg = "#B45309"
            accent_bar_color = "#F59E0B"
        elif status == "COMPLETED":
            badge_text = "✅ 조리 완료"
            badge_bg = "#D1FAE5"  # 은은한 에메랄드 그린
            badge_fg = "#047857"
            accent_bar_color = "#10B981"
        else:
            badge_text = f"📦 {status}"
            badge_bg = "#DBEAFE"
            badge_fg = "#1D4ED8"
            accent_bar_color = "#3B82F6"

        # 기존 카드 목록 확인 (새 카드를 항상 최상단에 배치하기 위해 before 옵션 사용)
        existing_cards = list(self.scrollable_frame.winfo_children())

        # 카드 컨테이너 (피드 최상단 삽입)
        card = tk.Frame(
            self.scrollable_frame,
            bg="#FFFFFF",
            bd=0,
            highlightthickness=1,
            highlightbackground="#E2E8F0",
        )
        if existing_cards:
            card.pack(fill=tk.X, padx=10, pady=(6, 4), side=tk.TOP, before=existing_cards[0])
        else:
            card.pack(fill=tk.X, padx=10, pady=(6, 4), side=tk.TOP)

        # 좌측 포인트 액센트 바
        accent_bar = tk.Frame(card, bg=accent_bar_color, width=4)
        accent_bar.pack(side=tk.LEFT, fill=tk.Y)

        card_body = tk.Frame(card, bg="#FFFFFF", padx=10, pady=8)
        card_body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 1) 헤더 행: 매장명, 주문번호, 상태 배지
        header_row = tk.Frame(card_body, bg="#FFFFFF")
        header_row.pack(fill=tk.X, pady=(0, 4))

        title_lbl = tk.Label(
            header_row,
            text=f"{store_name}  [주문 #{order_id}]",
            font=self.font_card_store,
            bg="#FFFFFF",
            fg="#0F172A",
        )
        title_lbl.pack(side=tk.LEFT)

        badge_lbl = tk.Label(
            header_row,
            text=badge_text,
            font=self.font_card_badge,
            bg=badge_bg,
            fg=badge_fg,
            padx=6,
            pady=1,
        )
        badge_lbl.pack(side=tk.RIGHT)

        # 2) 메시지 본문
        msg_lbl = tk.Label(
            card_body,
            text=message,
            font=self.font_card_msg,
            bg="#FFFFFF",
            fg="#1E293B",
            anchor="w",
            justify="left",
            wraplength=280,
        )
        msg_lbl.pack(fill=tk.X, pady=(0, 2))

        # 3) 메뉴 요약
        summary_lbl = tk.Label(
            card_body,
            text=f"🍴 {summary_text}",
            font=self.font_card_summary,
            bg="#FFFFFF",
            fg="#64748B",
            anchor="w",
            justify="left",
            wraplength=280,
        )
        summary_lbl.pack(fill=tk.X, pady=(0, 4))

        # 4) 수신 시각 푸터
        time_lbl = tk.Label(
            card_body,
            text=f"수신 시각: {timestamp}",
            font=self.font_card_time,
            bg="#FFFFFF",
            fg="#94A3B8",
            anchor="e",
        )
        time_lbl.pack(fill=tk.X)

        # 최신 알림이 보이도록 상단으로 자동 스크롤
        self.canvas.yview_moveto(0.0)

    # -------------------------------------------------------------------------
    # GUI 큐 파이프라인 (비동기 수신 스레드 -> Tkinter 메인 스레드 안전 전달)
    # -------------------------------------------------------------------------
    def _poll_gui_queue(self) -> None:
        """100ms마다 GUI 큐를 비워 화면 프리징 없이 상태 및 카드를 업데이트합니다."""
        if not self.is_running:
            return

        try:
            while True:
                msg_type, payload = self.gui_queue.get_nowait()
                if msg_type == "CONN_STATUS":
                    self._set_connection_status(payload)
                elif msg_type == "PUSH_NOTIFICATION":
                    self._add_notification_card(payload)
        except queue.Empty:
            pass
        finally:
            if self.is_running:
                self.after(100, self._poll_gui_queue)

    def _set_connection_status(self, is_connected: bool) -> None:
        """하단 바 연결 상태 표시등 제거에 따른 안전 폴백."""
        pass

    # -------------------------------------------------------------------------
    # 순수 L4 TCP 소켓 비동기 수신 데몬 스레드 (Worker)
    # -------------------------------------------------------------------------
    def _tcp_receiver_worker(self) -> None:
        """
        1) 중앙 TCP 소켓 서버(SERVER_HOST:SERVER_PORT)에 연결
        2) ROLE: 'MOBILE' 역할 등록 패킷 송신
        3) 서버의 실시간 Push 패킷(NOTIFICATION_PUSH) 대기 및 gui_queue 적재
        4) 연결 해제 시 자동 재연결(RECONNECT_INTERVAL)
        """
        while self.is_running:
            sock: Optional[socket.socket] = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((SERVER_HOST, SERVER_PORT))
                self._sock = sock

                # 1. 모바일 클라이언트 역할 등록 (ROLE: MOBILE)
                reg_req = make_request(
                    action=ACTION_REGISTER,
                    payload={
                        "ROLE": ROLE_MOBILE,
                        "client_type": "mobile",
                        "device_name": "Virtual-Galaxy-S24",
                    },
                    auth_token=SHARED_API_KEY,
                )
                send_packet(sock, reg_req)

                # 연결 상태 성공 보고
                self.gui_queue.put(("CONN_STATUS", True))

                # 2. 실시간 푸시 패킷 수신 루프
                # recv 타임아웃을 짧게 주어 프로그램 종료 시 반응성을 확보합니다.
                sock.settimeout(1.0)
                while self.is_running:
                    try:
                        msg = recv_packet(sock)
                    except socket.timeout:
                        continue

                    if msg is None:
                        # 서버가 정상 연결 종료
                        break

                    # 푸시 알림 패킷 검증 및 파싱
                    action = msg.get("action")
                    msg_type = msg.get("type")

                    if action == ACTION_NOTIFICATION_PUSH or msg_type == "NOTIFICATION":
                        # 데이터 정규화: 최상위 필드 또는 data 필드 우선 참조
                        inner_data = msg.get("data") if isinstance(msg.get("data"), dict) else {}
                        order_id = inner_data.get("order_id") or msg.get("order_id")
                        store_name = inner_data.get("store_name") or msg.get("store_name") or "보다수 매장"
                        status = inner_data.get("status") or msg.get("status") or "COOKING"
                        summary_text = inner_data.get("summary_text") or msg.get("summary_text") or ""
                        message_txt = inner_data.get("message") or msg.get("message") or ""
                        ts = inner_data.get("timestamp") or msg.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        card_data = {
                            "order_id": order_id,
                            "store_name": store_name,
                            "status": status,
                            "summary_text": summary_text,
                            "message": message_txt,
                            "timestamp": ts,
                        }
                        self.gui_queue.put(("PUSH_NOTIFICATION", card_data))

                    elif action == ACTION_ORDER_STATUS_BROADCAST:
                        # 하위 호환용 상태 브로드캐스트 처리
                        inner_data = msg.get("data") if isinstance(msg.get("data"), dict) else {}
                        order_id = inner_data.get("order_id") or msg.get("order_id")
                        status = inner_data.get("new_status") or inner_data.get("status") or msg.get("status")
                        if status in ("COOKING", "COMPLETED"):
                            card_data = {
                                "order_id": order_id,
                                "store_name": "보다수 매장",
                                "status": status,
                                "summary_text": "주문 메뉴",
                                "message": msg.get("message", f"주문 #{order_id} 상태: {status}"),
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                            self.gui_queue.put(("PUSH_NOTIFICATION", card_data))

            except Exception:
                pass
            finally:
                self._sock = None
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                if self.is_running:
                    self.gui_queue.put(("CONN_STATUS", False))
                    time.sleep(RECONNECT_INTERVAL)

    def _on_close(self) -> None:
        """창 종료 시 리소스 안전 해제."""
        self.is_running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self.destroy()


if __name__ == "__main__":
    app = VirtualMobileClient()
    app.mainloop()
