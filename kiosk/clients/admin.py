"""관리자 로그인과 비밀번호 변경 UI. 비밀번호 저장은 admin_auth에 위임한다."""
import queue
import threading
import time
import customtkinter as ctk

from kiosk.admin_auth import AdminCredentials
from .ui import BG, WHITE, MUTED, GREEN, ORANGE, Dialog, label, button


class PasswordForm(ctk.CTkFrame):
    def __init__(self, parent, credentials, on_success, changing=False):
        super().__init__(parent, fg_color=WHITE, corner_radius=18)
        self.credentials = credentials
        self.on_success = on_success
        self.changing = changing
        self.results = queue.Queue()
        self.busy = False
        self.failures = 0
        self.blocked_until = 0
        self.entries = []
        self.initialized = False
        label(self, '관리자 비밀번호 변경' if changing else '관리자 로그인', 26, bold=True).pack(padx=24, pady=(26, 10))
        label(self, '현재 비밀번호를 확인한 후 변경합니다.' if changing else '매장 운영 화면에 접속합니다.', 15, MUTED).pack(pady=(0, 14))
        prompts = ['현재 비밀번호', '새 비밀번호 (8자 이상)', '새 비밀번호 확인'] if changing else ['비밀번호']
        for prompt in prompts:
            entry = ctk.CTkEntry(self, placeholder_text=prompt, show='●', height=46,
                                 font=('Malgun Gothic', 16), width=360)
            entry.pack(fill='x', padx=26, pady=6)
            entry.bind('<Return>', lambda event: self.submit())
            self.entries.append(entry)
        self.status = label(self, '설정 확인 중…', 14, MUTED, wraplength=360, height=50)
        self.status.pack(fill='x', padx=26, pady=8)
        self.submit_button = button(self, '변경 사항 저장' if changing else '로그인', self.submit, height=52, state='disabled')
        self.submit_button.pack(fill='x', padx=26, pady=(4, 26))
        self.timer = self.after(100, self.drain_results)
        threading.Thread(target=self._initialize, daemon=True).start()

    def _initialize(self):
        try:
            data = self.credentials.initialize()
            self.results.put(('ready', data['ADMIN_PASSWORD_INITIAL'] == '1'))
        except (OSError, RuntimeError, ValueError):
            self.results.put(('fatal', '관리자 설정을 읽을 수 없습니다. .env.admin 파일을 확인해주세요.'))

    def submit(self):
        if not self.initialized or self.busy or time.monotonic() < self.blocked_until:
            return
        values = [entry.get() for entry in self.entries]
        if any(not value for value in values):
            self.status.configure(text='모든 비밀번호 항목을 입력해주세요.', text_color=ORANGE)
            return
        if any(len(value) > 128 for value in values):
            self.status.configure(text='비밀번호는 128자 이하로 입력해주세요.', text_color=ORANGE)
            return
        self.busy = True
        self.submit_button.configure(state='disabled')
        self.status.configure(text='확인 중입니다…', text_color=MUTED)
        threading.Thread(target=self._verify, args=(values,), daemon=True).start()

    def _verify(self, values):
        try:
            if self.changing:
                self.credentials.change_password(*values)
                initial = False
            else:
                initial = self.credentials.authenticate(values[0])
            self.results.put(('success', initial))
        except ValueError as exc:
            self.results.put(('error', str(exc)))
        except (OSError, RuntimeError):
            self.results.put(('error', '설정 파일 처리에 실패했습니다. 기존 설정을 확인해주세요.'))

    def drain_results(self):
        try:
            while True:
                kind, value = self.results.get_nowait()
                if kind == 'ready':
                    self.initialized = True
                    self.status.configure(text='초기 비밀번호 사용 중입니다. 로그인 후 변경해주세요.' if value else '', text_color=ORANGE if value else MUTED)
                    self.submit_button.configure(state='normal')
                    self.entries[0].focus_set()
                elif kind == 'fatal':
                    self.status.configure(text=value, text_color=ORANGE)
                elif kind == 'success':
                    for entry in self.entries:
                        entry.delete(0, 'end')
                    self.on_success(value)
                    return
                elif kind == 'error':
                    self.busy = False
                    self.failures += 1
                    for entry in self.entries:
                        entry.delete(0, 'end')
                    self.status.configure(text=value, text_color=ORANGE)
                    if self.failures >= 5:
                        self.blocked_until = time.monotonic() + 30
                        self.failures = 0
                    else:
                        self.submit_button.configure(state='normal')
        except queue.Empty:
            pass
        if self.blocked_until:
            remaining = self.blocked_until - time.monotonic()
            if remaining > 0:
                self.status.configure(text=f'반복 입력으로 잠시 대기합니다. {int(remaining) + 1}초 후 다시 시도해주세요.', text_color=ORANGE)
            else:
                self.blocked_until = 0
                self.status.configure(text='다시 입력할 수 있습니다.', text_color=MUTED)
                self.submit_button.configure(state='normal')
        self.timer = self.after(100, self.drain_results)

    def destroy(self):
        self.after_cancel(self.timer)
        super().destroy()


class AdminLogin(ctk.CTk):
    def __init__(self, credentials=None):
        super().__init__()
        ctk.set_appearance_mode('light')
        self.title('보다수 · 관리자 로그인')
        self.configure(fg_color=BG)
        self.geometry('490x470')
        self.resizable(False, False)
        self.authenticated = False
        self.initial_password = False
        label(self, 'BODASU  /  ADMIN', 15, GREEN, True).pack(pady=(24, 12))
        self.form = PasswordForm(self, credentials or AdminCredentials(), self._success)
        self.form.pack(fill='both', expand=True, padx=24, pady=(0, 24))

    def _success(self, initial):
        self.authenticated = True
        self.initial_password = initial
        self.destroy()

    def destroy(self):
        # 로그인 전용 Tk 인터프리터의 DPI/테마 타이머가 다음 창까지 남지 않게 한다.
        for timer in self.tk.call('after', 'info'):
            self.after_cancel(timer)
        super().destroy()


def require_login():
    window = AdminLogin()
    window.mainloop()
    return window.authenticated


def show_password_settings(parent):
    dialog = Dialog(parent, '관리자 비밀번호 변경', height=560)

    def success(initial):
        form.pack_forget()
        label(dialog, '비밀번호를 변경했습니다.', 25, GREEN, True).pack(pady=(90, 20))
        label(dialog, '다음 로그인부터 새 비밀번호를 사용하세요.', 16, MUTED).pack(pady=10)
        button(dialog, '확인', dialog.destroy).pack(fill='x', padx=36, pady=30)

    form = PasswordForm(dialog, AdminCredentials(), success, changing=True)
    form.pack(fill='both', expand=True, padx=12, pady=12)
    return dialog
