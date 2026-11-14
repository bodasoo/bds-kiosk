"""
[통합 실행 런처 - run_all.py]
- 중앙 서버(server.py), 주방 화면(kitchen_client.py),
  키오스크 2종(kiosk_client1.py, kiosk_client2.py)을 한 번에 비동기로 실행합니다.
- 이미 중앙 서버(8443 포트)가 실행 중이면 중복 실행([Errno 10048])을 건너뛰고
  기존 서버에 맞춰 클라이언트 창들만 띄웁니다.
"""

import os
import socket
import subprocess
import sys
import time
from typing import List

from config import BASE_DIR, SERVER_HOST, SERVER_PORT

PREFERRED_PYTHON_PATH = r"C:\Users\dayoung\OneDrive - 조선대학교\바탕 화면\python.exe"
CLIENT_SCRIPTS: List[str] = [
    "kitchen_client.py",
    "kiosk_client1.py",
    "kiosk_client2.py",
]


def resolve_python_executable() -> str:
    """프로젝트 패키지가 설치된 Python 인터프리터 경로를 반환합니다."""
    if os.path.exists(PREFERRED_PYTHON_PATH):
        return PREFERRED_PYTHON_PATH
    return sys.executable


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """지정된 호스트와 포트가 이미 열려 있는지 확인합니다."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, timeout_sec: float = 3.0) -> bool:
    """서버 포트가 열릴 때까지 최대 timeout_sec 초 동안 대기합니다."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if is_port_open(host, port, timeout=0.3):
            return True
        time.sleep(0.2)
    return is_port_open(host, port, timeout=0.3)


def launch_server_if_needed(python_exe: str) -> None:
    """중앙 서버가 아직 실행되지 않은 경우 별도 콘솔 창으로 기동합니다."""
    if is_port_open(SERVER_HOST, SERVER_PORT):
        print(
            f"[SKIP] 중앙 서버가 이미 {SERVER_HOST}:{SERVER_PORT} 포트에서 실행 중입니다."
        )
        return

    server_path = os.path.join(BASE_DIR, "server.py")
    if not os.path.exists(server_path):
        print(f"[ERROR] 서버 파일을 찾을 수 없습니다: {server_path}")
        return

    print(f"[START] 중앙 서버(server.py)를 새 콘솔 창에서 시작합니다...")
    creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
    subprocess.Popen(
        [python_exe, server_path],
        cwd=BASE_DIR,
        creationflags=creation_flags,
    )

    if wait_for_port(SERVER_HOST, SERVER_PORT, timeout_sec=3.0):
        print(f"[OK] 중앙 서버({SERVER_HOST}:{SERVER_PORT}) 준비 완료!")
    else:
        print(
            f"[WARN] 중앙 서버 응답 대기 시간(3초)을 초과했습니다. 서버 창 로그를 확인해 주세요."
        )


def launch_clients(python_exe: str) -> None:
    """주방 화면과 키오스크 1·2 클라이언트를 독립된 비블로킹 프로세스로 실행합니다."""
    creation_flags = (
        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    )
    for script_name in CLIENT_SCRIPTS:
        script_path = os.path.join(BASE_DIR, script_name)
        if not os.path.exists(script_path):
            print(f"[WARN] 클라이언트 파일을 찾을 수 없어 건너뜁니다: {script_path}")
            continue

        print(f"[START] {script_name} 실행 중...")
        subprocess.Popen(
            [python_exe, script_path],
            cwd=BASE_DIR,
            creationflags=creation_flags,
        )


def main() -> None:
    python_exe = resolve_python_executable()
    print("============================================================")
    print(" 🚀 보다수 멀티 키오스크 & 주방 시스템 통합 실행 (run_all.py)")
    print(f" • 사용 Python: {python_exe}")
    print(f" • 작업 폴더:   {BASE_DIR}")
    print("============================================================")

    launch_server_if_needed(python_exe)
    launch_clients(python_exe)

    print("============================================================")
    print(" ✅ 모든 프로그램 실행 요청을 완료했습니다! (터미널 점유 없음)")
    print("============================================================")


if __name__ == "__main__":
    main()

