"""統一 DB backend — 自動切換 SQLite (本地) 或 PostgreSQL (Supabase 雲端)。

切換條件：
- 環境變數 / Streamlit secret `DATABASE_URL` 有設 → 用 PostgreSQL
- 否則用 SQLite（向後兼容）

關鍵設計：用 PgConnAdapter wrap psycopg connection，
令所有現存使用 sqlite3 API 嘅 code（con.execute / cur.fetchall /
cur.lastrowid）都唔需要改。

SQL 自動翻譯：
- ?            → %s
- INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
- INSERT 自動加 RETURNING * 以模擬 lastrowid
- TEXT DEFAULT CURRENT_TIMESTAMP → TIMESTAMP DEFAULT CURRENT_TIMESTAMP
"""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def _resolve_database_url() -> str:
    """優先順序：環境變數 > .env > Streamlit secrets"""
    url = os.getenv("DATABASE_URL", "")
    if url:
        return url
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
    except Exception:
        pass
    return url or ""


DATABASE_URL = _resolve_database_url()
IS_POSTGRES = bool(DATABASE_URL)


# ============================================================
# SQL ADAPTER（SQLite → PostgreSQL 翻譯）
# ============================================================

def adapt_sql(sql: str) -> str:
    """將 SQLite SQL 翻譯成 PG 兼容"""
    if not IS_POSTGRES:
        return sql
    out = sql
    # 1. 參數佔位符
    out = out.replace("?", "%s")
    # 2. AUTOINCREMENT → SERIAL
    out = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "SERIAL PRIMARY KEY",
        out, flags=re.IGNORECASE,
    )
    # 3. TEXT DEFAULT CURRENT_TIMESTAMP → TIMESTAMP
    out = re.sub(
        r"TEXT\s+DEFAULT\s+CURRENT_TIMESTAMP",
        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        out, flags=re.IGNORECASE,
    )
    # 4. INSERT OR IGNORE → INSERT (caller 須加 ON CONFLICT DO NOTHING)
    out = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO",
        "INSERT INTO",
        out, flags=re.IGNORECASE,
    )
    # 5. strftime('%Y-%m', col) → TO_CHAR(col::date, 'YYYY-MM')
    out = re.sub(
        r"strftime\(\s*['\"]%Y-%m['\"]\s*,\s*([^)]+)\)",
        r"TO_CHAR((\1)::date, 'YYYY-MM')",
        out, flags=re.IGNORECASE,
    )
    # 6. strftime('%Y', col) → TO_CHAR(col::date, 'YYYY')
    out = re.sub(
        r"strftime\(\s*['\"]%Y['\"]\s*,\s*([^)]+)\)",
        r"TO_CHAR((\1)::date, 'YYYY')",
        out, flags=re.IGNORECASE,
    )
    # 7. strftime('%Y-%m-%d', col) → TO_CHAR(col::date, 'YYYY-MM-DD')
    out = re.sub(
        r"strftime\(\s*['\"]%Y-%m-%d['\"]\s*,\s*([^)]+)\)",
        r"TO_CHAR((\1)::date, 'YYYY-MM-DD')",
        out, flags=re.IGNORECASE,
    )
    return out


# ============================================================
# CONNECTION WRAPPERS
# ============================================================

class PgCursorAdapter:
    """模擬 sqlite3 cursor API，特別處理 lastrowid"""

    def __init__(self, pg_cursor, captured_first_row=None):
        self._cur = pg_cursor
        # 若 INSERT ... RETURNING * 已執行，第一條 row 預先 fetch 咗
        self._captured = captured_first_row
        self._captured_id = None
        if captured_first_row:
            # 取第一個欄位值當 last insert id
            keys = list(captured_first_row.keys())
            if keys:
                self._captured_id = captured_first_row[keys[0]]

    @property
    def lastrowid(self):
        """模擬 sqlite3 cursor.lastrowid"""
        return self._captured_id

    def fetchall(self):
        results = []
        if self._captured is not None:
            results.append(self._captured)
            self._captured = None
        try:
            more = self._cur.fetchall()
            results.extend(more)
        except Exception:
            pass
        return results

    def fetchone(self):
        if self._captured is not None:
            r = self._captured
            self._captured = None
            return r
        try:
            return self._cur.fetchone()
        except Exception:
            return None

    def __iter__(self):
        if self._captured is not None:
            yield self._captured
            self._captured = None
        try:
            for row in self._cur:
                yield row
        except Exception:
            pass


class PgConnAdapter:
    """模擬 sqlite3.Connection API 包住 psycopg connection"""

    def __init__(self, pg_conn):
        self._con = pg_conn

    def execute(self, sql, params=()):
        """模擬 sqlite3 con.execute() — INSERT 自動 RETURNING *"""
        sql_adapted = adapt_sql(sql)
        cur = self._con.cursor()

        # 偵測 INSERT 且未有 RETURNING → 自動加 RETURNING *
        stripped = sql_adapted.lstrip()
        is_insert = stripped.upper().startswith("INSERT")
        has_returning = "RETURNING" in sql_adapted.upper()
        captured = None

        if is_insert and not has_returning:
            # 加 RETURNING *
            sql_to_run = sql_adapted.rstrip().rstrip(";") + " RETURNING *"
            try:
                cur.execute(sql_to_run, tuple(params) if params else None)
                # 捕捉第一條 row 攞 id
                try:
                    captured = cur.fetchone()
                except Exception:
                    captured = None
            except Exception as ex:
                # 某啲 INSERT 唔可以 RETURNING（如 ON CONFLICT 無新 row）
                # → fallback 跑原 SQL，無 returning
                if "ON CONFLICT" in sql_adapted.upper():
                    # 重新跑唔加 RETURNING
                    self._con.rollback()
                    cur = self._con.cursor()
                    try:
                        cur.execute(
                            sql_adapted,
                            tuple(params) if params else None
                        )
                    except Exception:
                        raise ex
                else:
                    raise
        else:
            cur.execute(sql_adapted, tuple(params) if params else None)

        return PgCursorAdapter(cur, captured)

    def executescript(self, script):
        """模擬 sqlite3 executescript（PG 唔支援多 statement）

        每條 statement 用獨立 transaction（commit/rollback per statement），
        確保「already exists」之類嘅錯誤唔會清走之前成功嘅 DDL。
        """
        script_adapted = adapt_sql(script)
        # 簡易 split by ;（我哋 schema 簡單，無 trigger / DO block）
        statements = []
        for raw in script_adapted.split(";"):
            cleaned = "\n".join(
                line for line in raw.split("\n")
                if line.strip() and not line.strip().startswith("--")
            ).strip()
            if cleaned:
                statements.append(cleaned)

        for stmt in statements:
            cur = self._con.cursor()
            try:
                cur.execute(stmt)
                self._con.commit()  # 即時 commit 避免被後續錯誤拖累
            except Exception as ex:
                self._con.rollback()
                msg = str(ex).lower()
                # 預期嘅幂等錯誤 → 靜默跳過
                if ("already exists" in msg
                        or "does not exist" in msg):
                    continue
                raise

    def commit(self):
        self._con.commit()

    def rollback(self):
        self._con.rollback()

    def close(self):
        self._con.close()


# ============================================================
# CONNECTION CONTEXT MANAGER
# ============================================================

@contextmanager
def get_conn(sqlite_path: str | Path):
    """跨 backend 嘅 connection context manager。

    用法：
        with get_conn(SQLITE_PATH) as con:
            con.execute(...)
            cur = con.execute(...)
            cur.lastrowid  # works for both
    """
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        con = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            autocommit=False,
            connect_timeout=20,
        )
        adapter = PgConnAdapter(con)
        try:
            yield adapter
            adapter.commit()
        except Exception:
            adapter.rollback()
            raise
        finally:
            adapter.close()
    else:
        con = sqlite3.connect(str(sqlite_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()


def banner() -> str:
    if IS_POSTGRES:
        masked = re.sub(r":[^:@]+@", ":****@", DATABASE_URL)
        return f"🐘 PostgreSQL (Supabase) — {masked}"
    return "🪶 SQLite (本地)"
