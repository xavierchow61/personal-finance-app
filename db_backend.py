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
# PER-USER SCHEMA ISOLATION（PostgreSQL only）
# 每個用戶用獨立 PG schema 隔離資料，避免互相睇到對方資料
# ============================================================

def _sanitize_schema_name(raw: str) -> str:
    """將任意 user id / email 轉為合法 PG identifier"""
    if not raw:
        return ""
    # 只保留 a-z 0-9 _，其餘變 _，總長度限制 50
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", raw.lower())
    safe = re.sub(r"_+", "_", safe).strip("_")
    return f"user_{safe[:50]}" if safe else ""


def _current_user_schema(explicit_user_id: str | None = None) -> str | None:
    """取得當前登入用戶嘅專屬 schema 名稱。

    Args:
        explicit_user_id: 由 caller 顯式傳入（例：worker thread 冇 ScriptRunContext
                          就要靠 caller 提供）。優先用 explicit。

    Fallback：從 Streamlit session_state.auth_user 攞。

    回傳「user_<sanitized id>」格式；冇 user 或唔係 PG 模式 → None
    """
    if not IS_POSTGRES:
        return None
    # 1. 優先用 explicit 傳入嘅 id
    if explicit_user_id:
        return _sanitize_schema_name(explicit_user_id)
    # 2. Fallback：由 session_state 攞
    try:
        import streamlit as st
        user = st.session_state.get("auth_user")
        if not user:
            return None
        if isinstance(user, dict):
            raw = user.get("id") or user.get("email") or ""
            if "@" in raw:
                raw = raw.split("@")[0]
        else:
            raw = str(user)
        return _sanitize_schema_name(raw)
    except Exception:
        return None


# Context-local storage for worker threads（ThreadPoolExecutor）
import threading
_thread_user_id = threading.local()


def set_thread_user_id(user_id: str | None):
    """喺 worker thread 內設定當前用戶 id，畀 get_conn() 自動 pick up。

    用法（喺 ThreadPoolExecutor 入面）：
        uid = auth.get_current_user_id()
        def worker():
            set_thread_user_id(uid)
            try:
                return some_db_query()
            finally:
                set_thread_user_id(None)
    """
    if user_id:
        _thread_user_id.value = user_id
    else:
        if hasattr(_thread_user_id, 'value'):
            del _thread_user_id.value


def _get_thread_user_id() -> str | None:
    return getattr(_thread_user_id, 'value', None)


# 已初始化過 schema 嘅集合（避免每次 connect 都 CREATE SCHEMA）
_INITIALIZED_SCHEMAS: set[str] = set()


def _ensure_user_schema_exists(schema_name: str) -> None:
    """確保 schema 存在（per-process 只執行一次 per schema）。

    用獨立 autocommit connection 做 DDL，避免影響後續 query 嘅 transaction。
    重要：Transaction Pooler 模式下，DDL 一定要喺自己嘅 connection 做，
    唔可以同 query 共用（commit 會釋放 connection，下一條 statement 失去 schema）
    """
    if schema_name in _INITIALIZED_SCHEMAS:
        return
    import psycopg
    try:
        con = psycopg.connect(
            DATABASE_URL,
            autocommit=True,
            connect_timeout=20,
        )
        try:
            with con.cursor() as cur:
                cur.execute(
                    f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            _INITIALIZED_SCHEMAS.add(schema_name)
        finally:
            con.close()
    except Exception as ex:
        print(f"[db_backend] CREATE SCHEMA {schema_name} failed: {ex}")
        raise


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
    # 8. GROUP_CONCAT(expr, separator) → STRING_AGG(expr::text, separator)
    # SQLite: GROUP_CONCAT(col, '|')
    # PG:     STRING_AGG(col::text, '|')
    # PG 要求 STRING_AGG 第一 arg 係 text，所以加 ::text cast
    def _convert_group_concat(m):
        args = m.group(1).strip()
        # 分開最後一個 , 為 separator（如有）
        # GROUP_CONCAT(expr) → STRING_AGG(expr::text, ',') (default)
        # GROUP_CONCAT(expr, sep) → STRING_AGG(expr::text, sep)
        # 用平衡括號邏輯做簡易分隔
        depth = 0
        last_comma = -1
        in_str = False
        str_char = None
        for i, ch in enumerate(args):
            if in_str:
                if ch == str_char:
                    in_str = False
                continue
            if ch in ("'", '"'):
                in_str = True
                str_char = ch
                continue
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ',' and depth == 0:
                last_comma = i
        if last_comma >= 0:
            expr = args[:last_comma].strip()
            sep = args[last_comma + 1:].strip()
        else:
            expr = args
            sep = "','"
        return f"STRING_AGG(({expr})::text, {sep})"

    out = re.sub(
        r"GROUP_CONCAT\(((?:[^()]|\([^()]*\))*)\)",
        _convert_group_concat,
        out, flags=re.IGNORECASE,
    )
    # 9. IFNULL → COALESCE (SQLite-only function)
    out = re.sub(r"\bIFNULL\b", "COALESCE", out, flags=re.IGNORECASE)
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

    def __init__(self, pg_conn, user_schema: str | None = None):
        self._con = pg_conn
        # Used by executescript to re-SET search_path after rollback
        self._user_schema = user_schema

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
            # 用 SAVEPOINT 包住 try，失敗時只 rollback 呢條 statement，
            # 唔會回滾整個 transaction 嘅 SET search_path
            try:
                cur.execute("SAVEPOINT sp_insert")
                cur.execute(sql_to_run, tuple(params) if params else None)
                try:
                    captured = cur.fetchone()
                except Exception:
                    captured = None
                cur.execute("RELEASE SAVEPOINT sp_insert")
            except Exception as ex:
                # 某啲 INSERT 唔可以 RETURNING（如 ON CONFLICT 無新 row）
                # → rollback 去 savepoint，重跑唔加 RETURNING
                if "ON CONFLICT" in sql_adapted.upper():
                    try:
                        cur.execute("ROLLBACK TO SAVEPOINT sp_insert")
                    except Exception:
                        pass
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
        """模擬 sqlite3 executescript。

        🔒 重要：用 SAVEPOINT 而非 commit/rollback per statement，
        保持喺同一個 transaction 入面（避免 Transaction Pooler 釋放 backend，
        令後續 statement 失去 search_path）
        """
        script_adapted = adapt_sql(script)
        statements = []
        for raw in script_adapted.split(";"):
            cleaned = "\n".join(
                line for line in raw.split("\n")
                if line.strip() and not line.strip().startswith("--")
            ).strip()
            if cleaned:
                statements.append(cleaned)

        for i, stmt in enumerate(statements):
            sp_name = f"sp_init_{i}"
            cur = self._con.cursor()
            try:
                cur.execute(f"SAVEPOINT {sp_name}")
                cur.execute(stmt)
                cur.execute(f"RELEASE SAVEPOINT {sp_name}")
            except Exception as ex:
                # Rollback 到 savepoint，唔影響其他成功嘅 DDL
                try:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
                except Exception:
                    pass
                msg = str(ex).lower()
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

        # === Step 1: 解析當前用戶 schema（require auth）===
        user_schema = _current_user_schema(_get_thread_user_id())
        if not user_schema:
            raise RuntimeError(
                "PostgreSQL mode requires an authenticated user "
                "before DB access. Please login first."
            )

        # === Step 2: 確保 schema 存在（獨立 autocommit connection）===
        # 重要：Transaction Pooler 模式下，CREATE SCHEMA 同 SET search_path
        # 唔可以 commit 後再做其他嘢，因為 commit 會令 pooler 釋放 backend
        _ensure_user_schema_exists(user_schema)

        # === Step 3: 開主 connection 做用戶 query ===
        con = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            autocommit=False,
            connect_timeout=20,
        )
        adapter = PgConnAdapter(con, user_schema=user_schema)
        try:
            # 🔒 SET search_path 喺 transaction 第一句執行，
            # 同用戶 query 一齊 commit 先釋放 connection
            with con.cursor() as cur:
                cur.execute(
                    f'SET LOCAL search_path TO "{user_schema}"')
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
