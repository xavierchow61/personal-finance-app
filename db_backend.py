"""統一 DB backend — 自動切換 SQLite (本地) 或 PostgreSQL (Supabase 雲端)。

切換條件：
- 環境變數 / Streamlit secret `DATABASE_URL` 有設 → 用 PostgreSQL
- 否則用 SQLite（向後兼容）

提供：
- IS_POSTGRES：boolean flag
- get_conn(sqlite_path)：context manager 回傳 connection
- placeholder()：回傳 "?" 或 "%s"
- adapt_sql(sql)：將 SQLite SQL 改成 PostgreSQL 兼容
- exec_returning(cur, sql, params, returning_col)：execute + 取 last insert id
- executescript_compat(con, script)：跨後端執行 multi-statement script
"""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def _resolve_database_url() -> str:
    """優先順序：環境變數 > .env > Streamlit secrets"""
    # 1. 環境變數
    url = os.getenv("DATABASE_URL", "")
    if url:
        return url
    # 2. .env（透過 python-dotenv 已被 config.py 載入）
    # 3. Streamlit secrets
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", "")
    except Exception:
        pass
    return url or ""


DATABASE_URL = _resolve_database_url()
IS_POSTGRES = bool(DATABASE_URL)


def placeholder() -> str:
    """SQL 參數佔位符。SQLite 用 ?，PostgreSQL 用 %s"""
    return "%s" if IS_POSTGRES else "?"


def adapt_sql(sql: str) -> str:
    """將寫成 SQLite 風格的 SQL 自動轉換到 PostgreSQL 兼容。

    處理項目：
    - ?  →  %s（參數佔位符）
    - INTEGER PRIMARY KEY AUTOINCREMENT  →  SERIAL PRIMARY KEY
    - TEXT DEFAULT CURRENT_TIMESTAMP  →  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    - INTEGER DEFAULT 0/1（用於 boolean）：保留（PG 也接受 0/1 INT）
    - INSERT OR REPLACE → INSERT ... ON CONFLICT ... DO UPDATE
      （太複雜，由 caller 用 ON CONFLICT 直接寫）
    """
    if not IS_POSTGRES:
        return sql

    out = sql
    # 佔位符
    out = out.replace("?", "%s")
    # AUTOINCREMENT
    out = re.sub(
        r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
        "SERIAL PRIMARY KEY",
        out, flags=re.IGNORECASE,
    )
    # TEXT DEFAULT CURRENT_TIMESTAMP → TIMESTAMP（保留 default）
    out = re.sub(
        r"TEXT\s+DEFAULT\s+CURRENT_TIMESTAMP",
        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        out, flags=re.IGNORECASE,
    )
    # SQLite-only：PRAGMA — caller 須單獨處理
    return out


@contextmanager
def get_conn(sqlite_path: str | Path):
    """跨 backend 嘅 connection context manager。

    用法：
        with get_conn(SQLITE_PATH) as con:
            cur = con.execute("SELECT ...")  # SQLite
            # 或
            with con.cursor() as cur: cur.execute("SELECT ...")  # PG

    回傳嘅 connection 可以直接 con.execute() 或 con.cursor().execute()，
    視乎呼叫端。為簡化，建議全部用 con.cursor() 介面。
    """
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        con = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        try:
            yield con
            con.commit()
        finally:
            con.close()
    else:
        con = sqlite3.connect(str(sqlite_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()


def execute(con, sql: str, params: tuple | list | None = None):
    """跨 backend 嘅 execute helper。回傳 cursor。

    SQLite：con.execute(sql, params)
    PG：with con.cursor() → cur.execute(sql, params)，但為兼容直接用 con.cursor()
    """
    sql = adapt_sql(sql)
    if IS_POSTGRES:
        cur = con.cursor()
        cur.execute(sql, params or ())
        return cur
    else:
        return con.execute(sql, params or ())


def fetchall(con, sql: str, params: tuple | list | None = None) -> list[dict]:
    """執行 SELECT 並回傳 list[dict]。"""
    cur = execute(con, sql, params)
    rows = cur.fetchall()
    # PG 用 dict_row 已回傳 dict；SQLite 用 Row（dict-like）
    if IS_POSTGRES:
        return rows  # list[dict]
    return [dict(r) for r in rows]


def fetchone(con, sql: str, params: tuple | list | None = None) -> dict | None:
    cur = execute(con, sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    if IS_POSTGRES:
        return row
    return dict(row)


def insert_returning_id(con, sql: str, params: tuple | list,
                         returning_col: str = "id") -> int:
    """執行 INSERT 並回傳新建嘅 id。

    SQLite：用 cursor.lastrowid
    PG：用 RETURNING {returning_col}
    """
    sql = adapt_sql(sql)
    if IS_POSTGRES:
        # 在 SQL 後加 RETURNING（如果未有）
        if "returning" not in sql.lower():
            sql = sql.rstrip().rstrip(";") + f" RETURNING {returning_col}"
        cur = con.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[returning_col] if isinstance(row, dict) else row[0]
    else:
        cur = con.execute(sql, params)
        return cur.lastrowid


def executescript_compat(con, script: str):
    """執行 multi-statement script，跨後端兼容。

    SQLite：用 con.executescript()
    PG：split by ';' 再逐個 execute（避開 trigger / DO block 等複雜情況）
    """
    if IS_POSTGRES:
        # 簡化分割：找 ; 然後 newline 或結尾。實際 SCHEMA 內容簡單足夠。
        script = adapt_sql(script)
        cur = con.cursor()
        statements = [s.strip() for s in script.split(";") if s.strip()
                       and not s.strip().startswith("--")]
        for stmt in statements:
            # 過濾純註解行
            non_comment = "\n".join(
                line for line in stmt.split("\n")
                if line.strip() and not line.strip().startswith("--")
            )
            if non_comment.strip():
                cur.execute(non_comment)
    else:
        con.executescript(script)


def column_exists(con, table: str, column: str) -> bool:
    """檢查 table 有冇某條 column。SQLite 用 PRAGMA，PG 用 information_schema"""
    if IS_POSTGRES:
        cur = con.cursor()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            (table, column),
        )
        return cur.fetchone() is not None
    else:
        cols = {r["name"] for r in con.execute(
            f"PRAGMA table_info({table})").fetchall()}
        return column in cols


def banner() -> str:
    """回傳目前用緊邊個 backend 嘅 banner string，方便 debug"""
    if IS_POSTGRES:
        # 遮罩 password
        masked = re.sub(r":[^:@]+@", ":****@", DATABASE_URL)
        return f"🐘 PostgreSQL (Supabase) — {masked}"
    return "🪶 SQLite (本地)"
