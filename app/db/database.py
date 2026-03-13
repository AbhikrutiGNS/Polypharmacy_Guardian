"""
Single SQLite connection per thread (check_same_thread=False + WAL mode).
All queries go through get_db(). Connection is opened once at startup.
"""
import sqlite3
import threading
from app.config import DB_PATH

_local = threading.local()


def get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")   # 64 MB page cache
        conn.execute("PRAGMA temp_store=MEMORY")
        _local.conn = conn
    return _local.conn


def close_db() -> None:
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None
