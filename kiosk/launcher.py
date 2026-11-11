"""실행창이 시작한 서버와 키오스크 프로세스의 수명을 관리한다."""
from pathlib import Path
import os
import subprocess
import sys
import time
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
import webbrowser

import urllib3

from kiosk.config import BASE_DIR, BASE_URL
from kiosk.clients.ui import WHITE, MUTED, GREEN, ORANGE, label, button, setup_window
from kiosk.clients.api import server_available
from kiosk.clients.admin import show_password_settings


def run_launcher():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    root = ctk.CTk()
    setup_window(root, "보다수 · 매장 운영 센터", 1100, 700)
    processes = {}
    log_path = Path(BASE_DIR) / "logs" / "server.log"
    log_path.parent.mkdir(exist_ok=True)
    log = log_path.open("a", encoding="utf-8")

    def spawn(mode, output=None):
        return subprocess.Popen(
            [sys.executable, str(Path(BASE_DIR) / "app.py"), "--mode", mode],
            cwd=BASE_DIR,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            stdout=output,
            stderr=subprocess.STDOUT if output else None,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

    def open_store(mode):
        previous = processes.get(mode)
        if previous is None or previous.poll() is not None:
            processes[mode] = spawn(mode, log)

    def close():
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
        for process in processes.values():
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        log.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    header = ctk.CTkFrame(root, fg_color=WHITE, corner_radius=0)
    header.pack(fill='x')
    label(header, 'BODASU  /  STORE MANAGER', 14, GREEN, True).pack(anchor='w', padx=36, pady=(26, 8))
    label(header, '매장 운영 센터', 34, bold=True).pack(anchor='w', padx=36, pady=(0, 22))
    label(root, '사용할 화면을 선택해주세요', 24, bold=True).pack(anchor='w', padx=36, pady=(28, 8))
    status = label(root, '서버를 준비하고 있습니다…', 15, MUTED)
    status.pack(anchor='w', padx=36, pady=(0, 24))
    cards = ctk.CTkFrame(root, fg_color='transparent')
    cards.pack(fill='both', expand=True, padx=28)
    cards.grid_columnconfigure((0, 1, 2), weight=1, uniform='cards')
    cards.grid_rowconfigure(0, weight=1)
    buttons = []
    for column, (mode, name, english, description, color) in enumerate((
        ('coffee', '보다수 커피', '01  COFFEE', '음료 선택부터 주문 접수까지\n고객용 커피 키오스크', GREEN),
        ('gimbap', '김밥천국', '02  GIMBAP', '취향에 맞춘 든든한 한 끼\n고객용 식사 키오스크', ORANGE),
        ('kitchen', '주방 종합창', '03  KITCHEN', '두 매장 주문을 한눈에\n접수 · 조리 · 픽업 관리', '#364D6C'),
    )):
        card = ctk.CTkFrame(cards, fg_color=WHITE, corner_radius=20)
        card.grid(row=0, column=column, sticky='nsew', padx=8)
        label(card, english, 14, color, True).pack(anchor='w', padx=24, pady=(28, 24))
        label(card, name, 26, bold=True).pack(anchor='w', padx=24)
        label(card, description, 15, MUTED, justify='left').pack(anchor='w', padx=24, pady=14)
        control = button(card, '화면 열기  →', lambda mode=mode: open_store(mode), color=color, state='disabled', height=56)
        control.pack(side='bottom', fill='x', padx=24, pady=24)
        buttons.append(control)
    footer = ctk.CTkFrame(root, fg_color='transparent')
    footer.pack(side='bottom', fill='x', padx=36, pady=18, before=cards)
    button(footer, '관리자 비밀번호 변경', lambda: show_password_settings(root), secondary=True, width=200, height=40).pack(side='left')
    button(footer, '관리자 API 문서', lambda: webbrowser.open(f'{BASE_URL}/docs'), secondary=True, width=160, height=40).pack(side='right')

    started = time.monotonic()
    ready = False

    def check_server():
        nonlocal ready
        server = processes.get("server")
        if server is not None and server.poll() is not None:
            del processes["server"]
            server = None
        ready = server_available()
        if ready:
            connection_label = "서버 실행 중" if server else "기존 서버에 연결됨"
            status.configure(text=f"● {connection_label}  ·  화면을 열 수 있습니다.", text_color=GREEN)
        elif server is None:
            status.configure(text="서버에 연결할 수 없습니다. logs/server.log를 확인하세요.", text_color=ORANGE)
        elif time.monotonic() - started > 30:
            status.configure(text="서버 응답이 지연됩니다. logs/server.log를 확인하세요.", text_color=ORANGE)
        for control in buttons:
            control.configure(state=tk.NORMAL if ready else tk.DISABLED)
        for mode in ("coffee", "gimbap", "kitchen"):
            process = processes.get(mode)
            if process is not None and process.poll() is not None:
                if process.returncode:
                    messagebox.showerror("실행 오류", "매장 화면을 열지 못했습니다. logs/server.log를 확인하세요.")
                del processes[mode]
        root.after(500, check_server)

    try:
        if not server_available():
            processes["server"] = spawn("server", log)
        root.after(500, check_server)
        root.mainloop()
    finally:
        if not log.closed:
            close()
