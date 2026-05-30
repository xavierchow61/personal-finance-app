"""User settings store - 存於 personal_finance.db settings table"""
from . import db


def _ensure_table():
    db.init_db()
    from .db import _conn
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


def get(key: str, default=None) -> str | None:
    _ensure_table()
    from .db import _conn
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?",
                         (key,)).fetchone()
        return row["value"] if row else default


def set(key: str, value: str):
    _ensure_table()
    from .db import _conn
    with _conn() as c:
        c.execute("""
            INSERT INTO settings (key, value) VALUES (?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))


# === Convenience ===
def get_default_account() -> str:
    return get("default_account", "CASH") or "CASH"


def set_default_account(account_code: str):
    set("default_account", account_code)
