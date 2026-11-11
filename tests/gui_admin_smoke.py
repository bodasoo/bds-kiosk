"""임시 인증 파일로 실제 로그인·변경 폼을 검증한다. 운영 비밀번호는 변경하지 않는다."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kiosk.admin_auth import AdminCredentials
from kiosk.clients.admin import AdminLogin, show_password_settings


def wait_for(window, predicate):
    deadline = time.monotonic() + 10
    while not predicate() and time.monotonic() < deadline:
        window.update()
        time.sleep(0.01)
    assert predicate(), 'GUI condition timed out'


with tempfile.TemporaryDirectory() as directory:
    credentials = AdminCredentials(Path(directory) / '.env.admin')
    errors = []
    window = AdminLogin(credentials)
    window.report_callback_exception = lambda *args: errors.append(args)
    wait_for(window, lambda: window.form.initialized)
    window.form.entries[0].insert(0, 'wrong')
    window.form.submit()
    wait_for(window, lambda: not window.form.busy)
    assert not window.authenticated
    window.form.entries[0].insert(0, '1234')
    window.form.submit()
    wait_for(window, lambda: window.authenticated)

    # 실제 관리자 설정 팝업에서 저장 후 새 로그인까지 확인한다.
    window = AdminLogin(credentials)
    window.report_callback_exception = lambda *args: errors.append(args)
    wait_for(window, lambda: window.form.initialized)
    with patch('kiosk.clients.admin.AdminCredentials', return_value=credentials):
        dialog = show_password_settings(window)
    form = next(child for child in dialog.winfo_children() if hasattr(child, 'credentials'))
    wait_for(window, lambda: form.initialized)
    for entry, value in zip(form.entries, ['1234', 'Changed-password-2026', 'Changed-password-2026']):
        entry.insert(0, value)
    form.submit()
    wait_for(window, lambda: not form.winfo_manager())
    assert not credentials.authenticate('Changed-password-2026')
    dialog.destroy()
    window.form.entries[0].insert(0, 'Changed-password-2026')
    window.form.submit()
    wait_for(window, lambda: window.authenticated)
    assert not errors, errors
print('Admin GUI login, password change and new-password login passed.')
