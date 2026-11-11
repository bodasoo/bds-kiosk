import sqlite3
from kiosk.config import SQLITE_DB_PATH

def get_db_connection() -> sqlite3.Connection:
    """
    SQLite 데이터베이스 커넥션을 생성하여 반환합니다.
    - row_factory를 sqlite3.Row로 설정하여 딕셔너리 형태로 컬럼에 접근 가능합니다.
    - WAL 모드 및 외래키(Foreign Key) 제약조건을 활성화하여 다중 접속 동시성을 보장합니다.
    """
    conn = sqlite3.connect(SQLITE_DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn
