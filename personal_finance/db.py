"""Personal Finance database schemas + CRUD。

支援 SQLite (本地) + PostgreSQL (Supabase 雲端)。
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from config import BASE_DIR, get_personal_finance_db_path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_backend import get_conn, IS_POSTGRES


# 預設路徑（向後兼容）；實際讀寫時用 get_personal_finance_db_path()
DB_PATH = BASE_DIR / "personal_finance.db"


# === Account 類型 ===
ACCOUNT_TYPES = {
    "asset": "資產 (現金/銀行)",       # +ve balance = 你有錢
    "liability": "負債 (信用卡)",        # +ve balance = 你欠錢
    "expense": "開支 (消費類別)",       # +ve balance = 累計支出
    "income": "收入 (人工/紅利)",       # +ve balance = 累計收入
}

# Project 狀態
PROJECT_STATUSES = ["active", "completed", "cancelled"]


SCHEMA = """
-- ============ ACCOUNTS ============
CREATE TABLE IF NOT EXISTS accounts (
    code TEXT PRIMARY KEY,                    -- "CASH" / "VISA_HSBC" / "FOOD"
    name TEXT NOT NULL,                        -- 顯示名「現金」「HSBC Visa」「餐飲」
    account_type TEXT NOT NULL,                -- asset / liability / expense / income
    opening_balance REAL DEFAULT 0,
    currency TEXT DEFAULT 'HKD',
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    color TEXT,                                -- hex color for UI
    icon TEXT,                                 -- emoji or icon name
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============ PROJECTS ============
-- 必須喺 journal_entries 之前定義（因 FK 依賴）
CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                         -- 「日本旅行」「裝修廚房」
    description TEXT,
    start_date TEXT,
    end_date TEXT,
    total_budget REAL,
    status TEXT DEFAULT 'active',
    icon TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============ JOURNAL ENTRIES ============
CREATE TABLE IF NOT EXISTS journal_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    description TEXT,
    invoice_id INTEGER,                        -- link to invoices.db invoices.id
    project_id INTEGER,                        -- optional
    notes TEXT,
    currency TEXT DEFAULT 'HKD',               -- 多幣別
    fx_rate REAL DEFAULT 1.0,                  -- 對 HKD 嘅匯率
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_je_date ON journal_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_je_invoice ON journal_entries(invoice_id);
CREATE INDEX IF NOT EXISTS idx_je_project ON journal_entries(project_id);

-- ============ JOURNAL LINES ============
CREATE TABLE IF NOT EXISTS journal_lines (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    account_code TEXT NOT NULL,
    debit REAL DEFAULT 0,
    credit REAL DEFAULT 0,
    FOREIGN KEY (entry_id) REFERENCES journal_entries(entry_id) ON DELETE CASCADE,
    FOREIGN KEY (account_code) REFERENCES accounts(code)
);

CREATE INDEX IF NOT EXISTS idx_jl_entry ON journal_lines(entry_id);
CREATE INDEX IF NOT EXISTS idx_jl_account ON journal_lines(account_code);

-- ============ BUDGETS ============
CREATE TABLE IF NOT EXISTS budgets (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_code TEXT NOT NULL,                -- expense category code
    period TEXT NOT NULL,                       -- 'YYYY-MM' for monthly
                                                -- 'YYYY' for annual
                                                -- 'PROJECT:<id>' for project
    amount REAL NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_code, period),
    FOREIGN KEY (account_code) REFERENCES accounts(code)
);

CREATE INDEX IF NOT EXISTS idx_bud_period ON budgets(period);

-- ============ CLOSED PERIODS ============
-- 鎖定嘅月份 ('YYYY-MM')，係嘅 entry 唔可以新增 / 改 / 刪
CREATE TABLE IF NOT EXISTS closed_periods (
    period TEXT PRIMARY KEY,           -- 'YYYY-MM'
    closed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    closed_by TEXT,
    notes TEXT
);

-- ============ PAYMENT METHOD ALIASES ============
-- 用戶自訂 keyword (e.g. "AlipayHK 賬戶") → account code
CREATE TABLE IF NOT EXISTS payment_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    account_code TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(keyword),
    FOREIGN KEY (account_code) REFERENCES accounts(code)
);

-- ============ FX RATES ============
-- Currency conversion rates to base (HKD default)
CREATE TABLE IF NOT EXISTS fx_rates (
    fx_id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL,           -- "USD", "JPY", "CNY"
    rate_to_hkd REAL NOT NULL,         -- 1 USD = 7.8 HKD => 7.8
    as_of_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(currency, as_of_date)
);

-- ============ CREDIT CARDS ============
-- 信用卡額外資料（額度、結算日、還款日、利率…）
-- account_code 必須對應一個 type='liability' 嘅 account
-- 注意：rewards_rate / rewards_type 已內建（之前用 ALTER 加，
-- 但 PG 上唔可靠，索性放入 CREATE TABLE）
CREATE TABLE IF NOT EXISTS credit_cards (
    card_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_code TEXT UNIQUE NOT NULL,
    card_last4 TEXT,                            -- 「8989」
    credit_limit REAL,                          -- 信用額度（HKD）
    statement_day INTEGER,                      -- 月結日 1-31
    due_day INTEGER,                            -- 還款限期日 1-31
    interest_rate REAL,                         -- 年利率（例 0.32）
    annual_fee REAL,                            -- 年費
    rewards TEXT,                               -- 回贈/里數說明
    rewards_rate REAL,                          -- 預設回贈率（0.01 = 1%）
    rewards_type TEXT,                          -- "cash" / "miles" / "points"
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_code) REFERENCES accounts(code)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cc_account ON credit_cards(account_code);

-- ============ LOANS ============
-- 個人貸款：按揭/汽車/個人/信用卡分期
CREATE TABLE IF NOT EXISTS loans (
    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                         -- 「東亞按揭」「中銀汽車貸款」
    loan_type TEXT NOT NULL,                    -- mortgage/auto/personal/instalment
    bank TEXT,                                  -- 銀行/機構名
    principal REAL NOT NULL,                    -- 本金總額
    interest_rate REAL NOT NULL,                -- 年利率（例 0.045 = 4.5%）
    term_months INTEGER NOT NULL,               -- 還款期數（月）
    monthly_payment REAL,                       -- 每月應還（可由系統計算）
    start_date TEXT NOT NULL,                   -- 開始日
    due_day INTEGER,                            -- 每月還款日 1-31
    account_code TEXT,                          -- 對應 liability account（如有）
    status TEXT DEFAULT 'active',               -- active / paid / cancelled
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);
"""


@contextmanager
def _conn():
    """跨 backend connection（PG = Supabase；SQLite = 本地按用戶切換）"""
    db_path = get_personal_finance_db_path()
    with get_conn(db_path) as con:
        # PG 自動啟用 FK；SQLite 需要 PRAGMA
        if not IS_POSTGRES:
            con.execute("PRAGMA foreign_keys = ON")
        yield con


def _column_exists(con, table: str, column: str) -> bool:
    """跨 backend 檢查 column 存在"""
    if IS_POSTGRES:
        rows = con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=? AND column_name=?",
            (table, column),
        ).fetchall()
        return len(rows) > 0
    else:
        cols = {r["name"] for r in con.execute(
            f"PRAGMA table_info({table})").fetchall()}
        return column in cols


def _safe_add_column(con, table: str, column: str, defn: str):
    """安全加 column。已存在 / 表不存在 → 靜默跳過"""
    try:
        if _column_exists(con, table, column):
            return
        con.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {defn}"
        )
    except Exception:
        # 表唔存在或其他無法處理嘅錯 → 跳過
        if IS_POSTGRES:
            try:
                con.rollback()   # PG 失敗要清 transaction
            except Exception:
                pass


_INIT_DONE = False


def init_db(force: bool = False):
    """初始化 schema。已執行過則跳過（除非 force=True）。

    對 PG 嚟講，呢個 cache 重要：避免每次 CRUD 都跑 schema 檢查。
    """
    global _INIT_DONE
    if _INIT_DONE and not force:
        return
    _INIT_DONE = True   # 提前 set 避免 recursive call
    with _conn() as c:
        c.executescript(SCHEMA)
        # === 對舊 PG schema 嘅救援補丁 ===
        # 確保關鍵 column 一定存在（即使 SCHEMA 改動前已 deploy）
        _safe_add_column(c, "journal_entries",
                          "currency", "TEXT DEFAULT 'HKD'")
        _safe_add_column(c, "journal_entries",
                          "fx_rate", "REAL DEFAULT 1.0")
        _safe_add_column(c, "credit_cards",
                          "rewards_rate", "REAL")
        _safe_add_column(c, "credit_cards",
                          "rewards_type", "TEXT")
        # Migration：journal_entries 加 currency / fx_rate / hkd_amount
        if not _column_exists(c, "journal_entries", "currency"):
            c.execute("ALTER TABLE journal_entries ADD COLUMN "
                      "currency TEXT DEFAULT 'HKD'")
        if not _column_exists(c, "journal_entries", "fx_rate"):
            c.execute("ALTER TABLE journal_entries ADD COLUMN "
                      "fx_rate REAL DEFAULT 1.0")
        # Migration：credit_cards 表（保證舊 DB 都有）
        c.execute("""
            CREATE TABLE IF NOT EXISTS credit_cards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_code TEXT UNIQUE NOT NULL,
                card_last4 TEXT,
                credit_limit REAL,
                statement_day INTEGER,
                due_day INTEGER,
                interest_rate REAL,
                annual_fee REAL,
                rewards TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_code) REFERENCES accounts(code)
                    ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_cc_account
            ON credit_cards(account_code)
        """)
        # Migration：credit_cards 加 rewards_rate / rewards_type
        if not _column_exists(c, "credit_cards", "rewards_rate"):
            c.execute(
                "ALTER TABLE credit_cards ADD COLUMN "
                "rewards_rate REAL"
            )
        if not _column_exists(c, "credit_cards", "rewards_type"):
            c.execute(
                "ALTER TABLE credit_cards ADD COLUMN "
                "rewards_type TEXT"
            )
        # Migration：loans 表
        c.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                loan_type TEXT NOT NULL,
                bank TEXT,
                principal REAL NOT NULL,
                interest_rate REAL NOT NULL,
                term_months INTEGER NOT NULL,
                monthly_payment REAL,
                start_date TEXT NOT NULL,
                due_day INTEGER,
                account_code TEXT,
                status TEXT DEFAULT 'active',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_loans_status
            ON loans(status)
        """)


# ============================================================
# ACCOUNTS CRUD
# ============================================================
def list_accounts(active_only: bool = True,
                  account_type: str | None = None) -> list[dict]:
    init_db()
    sql = "SELECT * FROM accounts WHERE 1=1"
    params = []
    if active_only:
        sql += " AND is_active=1"
    if account_type:
        sql += " AND account_type=?"
        params.append(account_type)
    sql += " ORDER BY account_type, sort_order, code"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def get_account(code: str) -> dict | None:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM accounts WHERE code=?", (code,)).fetchone()
        return dict(row) if row else None


def upsert_account(code: str, name: str, account_type: str,
                    opening_balance: float = 0,
                    currency: str = "HKD",
                    is_active: bool = True,
                    sort_order: int = 0,
                    color: str | None = None,
                    icon: str | None = None,
                    notes: str | None = None):
    if account_type not in ACCOUNT_TYPES:
        raise ValueError(f"Invalid account_type: {account_type}")
    init_db()
    with _conn() as c:
        c.execute("""
            INSERT INTO accounts (code, name, account_type, opening_balance,
                                   currency, is_active, sort_order, color,
                                   icon, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name,
                account_type=excluded.account_type,
                opening_balance=excluded.opening_balance,
                currency=excluded.currency,
                is_active=excluded.is_active,
                sort_order=excluded.sort_order,
                color=excluded.color,
                icon=excluded.icon,
                notes=excluded.notes
        """, (code, name, account_type, opening_balance, currency,
              1 if is_active else 0, sort_order, color, icon, notes))


def delete_account(code: str):
    init_db()
    with _conn() as c:
        # 唔可以刪有 journal entry 嘅 account
        used = c.execute(
            "SELECT COUNT(*) FROM journal_lines WHERE account_code=?",
            (code,)).fetchone()[0]
        if used > 0:
            raise ValueError(f"Account {code} 有 {used} 個 journal lines，"
                              f"唔可以刪。可以 deactivate（is_active=0）代替。")
        c.execute("DELETE FROM accounts WHERE code=?", (code,))


# ============================================================
# JOURNAL ENTRIES
# ============================================================
def create_entry(entry_date: str | date,
                  description: str,
                  lines: list[dict],
                  invoice_id: int | None = None,
                  project_id: int | None = None,
                  notes: str | None = None,
                  currency: str = "HKD",
                  fx_rate: float | None = None) -> int:
    """建一個 journal entry（會驗證 Dr = Cr）

    Args:
        currency: entry 嘅原幣值 (HKD / USD / JPY ...)
        fx_rate: 1 unit of currency = ? HKD。None = 自動由 fx_rates table 攞
    """
    init_db()

    # Validate balance（喺原幣值層面）
    total_dr = sum(float(l.get("debit") or 0) for l in lines)
    total_cr = sum(float(l.get("credit") or 0) for l in lines)
    if abs(total_dr - total_cr) > 0.005:
        raise ValueError(
            f"Journal entry 唔平衡：Dr {total_dr:.2f} ≠ Cr {total_cr:.2f}")
    if not lines:
        raise ValueError("一個 entry 一定要至少 1 line")

    if isinstance(entry_date, date):
        entry_date = entry_date.isoformat()

    # Check period closed
    if is_period_closed(entry_date):
        period = entry_date[:7]
        raise ValueError(
            f"⚠️ Period {period} 已鎖定，唔可以新增 entry。\n"
            f"如要修改，請先去「⚙️ 設定 → 期間管理」重開該月份。"
        )

    # 自動攞 fx_rate
    currency = currency.upper()
    if fx_rate is None:
        fx_rate = get_fx_rate(currency, as_of_date=entry_date)

    with _conn() as c:
        cur = c.execute("""
            INSERT INTO journal_entries (entry_date, description,
                                          invoice_id, project_id, notes,
                                          currency, fx_rate)
            VALUES (?,?,?,?,?,?,?)
        """, (entry_date, description, invoice_id, project_id, notes,
              currency, fx_rate))
        entry_id = cur.lastrowid
        for l in lines:
            c.execute("""
                INSERT INTO journal_lines (entry_id, account_code, debit, credit)
                VALUES (?,?,?,?)
            """, (entry_id, l["account_code"],
                  float(l.get("debit") or 0),
                  float(l.get("credit") or 0)))
        return entry_id


def list_entries(start_date: str | None = None,
                 end_date: str | None = None,
                 account_code: str | None = None,
                 project_id: int | None = None,
                 invoice_id: int | None = None,
                 limit: int = 100) -> list[dict]:
    """列出 journal entries — 用 single JOIN + GROUP BY 取代 nested subquery
    優化前：32s（nested subquery 每行跑一次）
    優化後：~3s（單一 query + GROUP_CONCAT/STRING_AGG aggregate）
    """
    init_db()

    # 用 GROUP_CONCAT 直接 aggregate lines summary（adapt_sql 會自動翻譯 PG）
    sql = """
        SELECT je.entry_id, je.entry_date, je.description,
               je.invoice_id, je.project_id, je.notes,
               je.currency, je.fx_rate, je.created_at,
               GROUP_CONCAT(
                   jl.account_code || ':' ||
                   CASE WHEN jl.debit > 0
                        THEN 'Dr ' || jl.debit
                        ELSE 'Cr ' || jl.credit END,
                   ' | '
               ) AS lines_summary,
               MAX(jl.debit + jl.credit) AS amount
        FROM journal_entries je
        LEFT JOIN journal_lines jl ON jl.entry_id=je.entry_id
    """
    where_parts = []
    params = []
    if start_date:
        where_parts.append("je.entry_date >= ?")
        params.append(start_date)
    if end_date:
        where_parts.append("je.entry_date <= ?")
        params.append(end_date)
    if account_code:
        where_parts.append(
            "je.entry_id IN ("
            "SELECT entry_id FROM journal_lines WHERE account_code=?)"
        )
        params.append(account_code)
    if project_id is not None:
        where_parts.append("je.project_id = ?")
        params.append(project_id)
    if invoice_id is not None:
        where_parts.append("je.invoice_id = ?")
        params.append(invoice_id)

    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)

    sql += """
        GROUP BY je.entry_id, je.entry_date, je.description,
                 je.invoice_id, je.project_id, je.notes,
                 je.currency, je.fx_rate, je.created_at
        ORDER BY je.entry_date DESC, je.entry_id DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def get_entry(entry_id: int) -> dict | None:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM journal_entries WHERE entry_id=?",
                         (entry_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["lines"] = [dict(l) for l in c.execute(
            "SELECT * FROM journal_lines WHERE entry_id=? ORDER BY line_id",
            (entry_id,)).fetchall()]
        return d


def delete_entry(entry_id: int):
    init_db()
    with _conn() as c:
        # Check 個 entry 嘅 period 有冇 closed
        row = c.execute("SELECT entry_date FROM journal_entries WHERE entry_id=?",
                          (entry_id,)).fetchone()
        if row and row["entry_date"] and is_period_closed(row["entry_date"]):
            raise ValueError(
                f"⚠️ Entry #{entry_id} 喺鎖定 period ({row['entry_date'][:7]}) 入面，"
                f"唔可以刪。")
        c.execute("DELETE FROM journal_entries WHERE entry_id=?", (entry_id,))


# ============================================================
# BUDGETS
# ============================================================
def set_budget(account_code: str, period: str, amount: float,
               notes: str | None = None):
    """設或者 update budget。period 例子：'2026-06' / '2026' / 'PROJECT:1'"""
    init_db()
    with _conn() as c:
        c.execute("""
            INSERT INTO budgets (account_code, period, amount, notes)
            VALUES (?,?,?,?)
            ON CONFLICT(account_code, period) DO UPDATE SET
                amount=excluded.amount,
                notes=excluded.notes
        """, (account_code, period, amount, notes))


def get_budget(account_code: str, period: str) -> float | None:
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT amount FROM budgets WHERE account_code=? AND period=?",
            (account_code, period)).fetchone()
        return float(row["amount"]) if row else None


def list_budgets(period: str | None = None) -> list[dict]:
    init_db()
    sql = "SELECT * FROM budgets"
    params = []
    if period:
        sql += " WHERE period=?"
        params.append(period)
    sql += " ORDER BY account_code"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def delete_budget(budget_id: int):
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM budgets WHERE budget_id=?", (budget_id,))


# ============================================================
# PROJECTS
# ============================================================
def create_project(name: str, description: str | None = None,
                    start_date: str | None = None,
                    end_date: str | None = None,
                    total_budget: float | None = None,
                    icon: str | None = None) -> int:
    init_db()
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO projects (name, description, start_date, end_date,
                                   total_budget, icon)
            VALUES (?,?,?,?,?,?)
        """, (name, description, start_date, end_date, total_budget, icon))
        return cur.lastrowid


def list_projects(status: str | None = None) -> list[dict]:
    init_db()
    sql = "SELECT * FROM projects"
    params = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY status, project_id DESC"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def get_project(project_id: int) -> dict | None:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM projects WHERE project_id=?",
                         (project_id,)).fetchone()
        return dict(row) if row else None


def update_project(project_id: int, **fields):
    init_db()
    if not fields:
        return
    allowed = {"name", "description", "start_date", "end_date",
                "total_budget", "status", "icon"}
    sets = []
    params = []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(v)
    if not sets:
        return
    params.append(project_id)
    with _conn() as c:
        c.execute(f"UPDATE projects SET {', '.join(sets)} WHERE project_id=?",
                   params)


def delete_project(project_id: int):
    init_db()
    with _conn() as c:
        # Unlink entries first
        c.execute("UPDATE journal_entries SET project_id=NULL WHERE project_id=?",
                   (project_id,))
        # Delete project budgets
        c.execute("DELETE FROM budgets WHERE period=?", (f"PROJECT:{project_id}",))
        c.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


# ============================================================
# PAYMENT ALIASES
# ============================================================
def list_payment_aliases() -> list[dict]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM payment_aliases ORDER BY keyword").fetchall()
        return [dict(r) for r in rows]


def add_payment_alias(keyword: str, account_code: str,
                       notes: str | None = None):
    init_db()
    with _conn() as c:
        c.execute("""
            INSERT INTO payment_aliases (keyword, account_code, notes)
            VALUES (?,?,?)
            ON CONFLICT(keyword) DO UPDATE SET
                account_code=excluded.account_code,
                notes=excluded.notes
        """, (keyword.strip().lower(), account_code, notes))


def delete_payment_alias(alias_id: int):
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM payment_aliases WHERE alias_id=?", (alias_id,))


def lookup_payment_alias(payment_method: str | None) -> str | None:
    """揾用戶自訂嘅 alias。Return account_code or None"""
    if not payment_method:
        return None
    s = payment_method.lower().strip()
    init_db()
    with _conn() as c:
        # Exact match first
        row = c.execute(
            "SELECT account_code FROM payment_aliases WHERE keyword=?",
            (s,)).fetchone()
        if row:
            return row["account_code"]
        # Substring
        rows = c.execute("SELECT * FROM payment_aliases").fetchall()
        for r in rows:
            if r["keyword"] in s or s in r["keyword"]:
                return r["account_code"]
    return None


# ============================================================
# FX RATES (multi-currency support)
# ============================================================
def set_fx_rate(currency: str, rate_to_hkd: float,
                 as_of_date: str | None = None, notes: str | None = None):
    """設匯率：1 USD = rate_to_hkd HKD"""
    if as_of_date is None:
        from datetime import date
        as_of_date = date.today().isoformat()
    init_db()
    with _conn() as c:
        c.execute("""
            INSERT INTO fx_rates (currency, rate_to_hkd, as_of_date, notes)
            VALUES (?,?,?,?)
            ON CONFLICT(currency, as_of_date) DO UPDATE SET
                rate_to_hkd=excluded.rate_to_hkd,
                notes=excluded.notes
        """, (currency.upper(), rate_to_hkd, as_of_date, notes))


def get_fx_rate(currency: str, as_of_date: str | None = None) -> float:
    """攞最新嘅 rate。HKD 直接 return 1。"""
    if currency.upper() == "HKD":
        return 1.0
    init_db()
    with _conn() as c:
        if as_of_date:
            row = c.execute("""
                SELECT rate_to_hkd FROM fx_rates
                WHERE currency=? AND as_of_date<=?
                ORDER BY as_of_date DESC LIMIT 1
            """, (currency.upper(), as_of_date)).fetchone()
        else:
            row = c.execute("""
                SELECT rate_to_hkd FROM fx_rates
                WHERE currency=?
                ORDER BY as_of_date DESC LIMIT 1
            """, (currency.upper(),)).fetchone()
        if row:
            return float(row["rate_to_hkd"])
    # Default fallback rates（粗略，建議用戶設啱）
    fallbacks = {"USD": 7.8, "JPY": 0.05, "CNY": 1.08, "EUR": 8.5,
                  "GBP": 9.8, "TWD": 0.24, "KRW": 0.0055, "SGD": 5.8}
    return fallbacks.get(currency.upper(), 1.0)


# ============================================================
# CLOSED PERIODS
# ============================================================
def is_period_closed(entry_date: str) -> bool:
    """Check 個日期係咪喺 closed period 入面。"""
    if not entry_date or len(entry_date) < 7:
        return False
    period = entry_date[:7]  # YYYY-MM
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM closed_periods WHERE period=?", (period,)
        ).fetchone()
        return row is not None


def close_period(period: str, notes: str | None = None):
    """鎖定某月份（YYYY-MM 格式）"""
    init_db()
    with _conn() as c:
        c.execute("""
            INSERT INTO closed_periods (period, notes) VALUES (?,?)
            ON CONFLICT(period) DO UPDATE SET notes=excluded.notes
        """, (period, notes))


def reopen_period(period: str):
    """重開某月份"""
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM closed_periods WHERE period=?", (period,))


def list_closed_periods() -> list[dict]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM closed_periods ORDER BY period DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def list_fx_rates() -> list[dict]:
    init_db()
    with _conn() as c:
        # 最新嗰個 per currency
        rows = c.execute("""
            SELECT * FROM fx_rates fr1
            WHERE NOT EXISTS (
                SELECT 1 FROM fx_rates fr2
                WHERE fr2.currency=fr1.currency
                  AND fr2.as_of_date > fr1.as_of_date
            )
            ORDER BY currency
        """).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# CREDIT CARDS
# ============================================================
def list_credit_cards() -> list[dict]:
    """列出所有信用卡額外資料（JOIN accounts 帶埋名稱）

    若 credit_cards 表不存在（migration 未跑）→ 自動 init + 重試
    若仍失敗 → 回空 list（讓 UI 仍能渲染）
    """
    try:
        init_db()
        with _conn() as c:
            rows = c.execute("""
                SELECT cc.*, a.name AS account_name,
                       a.icon AS account_icon,
                       a.currency AS account_currency, a.is_active
                FROM credit_cards cc
                JOIN accounts a ON a.code = cc.account_code
                ORDER BY a.sort_order, a.name
            """).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        # Table doesn't exist or schema mismatch — return empty
        return []


def get_credit_card(account_code: str) -> dict | None:
    """揾某 account 嘅信用卡資料"""
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM credit_cards WHERE account_code=?",
            (account_code,),
        ).fetchone()
        return dict(row) if row else None


def upsert_credit_card(account_code: str,
                        card_last4: str | None = None,
                        credit_limit: float | None = None,
                        statement_day: int | None = None,
                        due_day: int | None = None,
                        interest_rate: float | None = None,
                        annual_fee: float | None = None,
                        rewards: str | None = None,
                        rewards_rate: float | None = None,
                        rewards_type: str | None = None,
                        notes: str | None = None):
    """新增 / 更新信用卡資料"""
    init_db()
    with _conn() as c:
        c.execute("""
            INSERT INTO credit_cards
              (account_code, card_last4, credit_limit, statement_day,
               due_day, interest_rate, annual_fee, rewards,
               rewards_rate, rewards_type, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(account_code) DO UPDATE SET
              card_last4=excluded.card_last4,
              credit_limit=excluded.credit_limit,
              statement_day=excluded.statement_day,
              due_day=excluded.due_day,
              interest_rate=excluded.interest_rate,
              annual_fee=excluded.annual_fee,
              rewards=excluded.rewards,
              rewards_rate=excluded.rewards_rate,
              rewards_type=excluded.rewards_type,
              notes=excluded.notes
        """, (account_code, card_last4, credit_limit, statement_day,
              due_day, interest_rate, annual_fee, rewards,
              rewards_rate, rewards_type, notes))


def delete_credit_card(account_code: str):
    """刪信用卡額外資料（唔影響原 account）"""
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM credit_cards WHERE account_code=?",
                   (account_code,))


# ============================================================
# LOANS
# ============================================================
def list_loans(status: str | None = None) -> list[dict]:
    """列出所有貸款（可按 status 篩）"""
    init_db()
    sql = "SELECT * FROM loans"
    params = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY status, start_date DESC"
    with _conn() as c:
        try:
            rows = c.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []


def get_loan(loan_id: int) -> dict | None:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM loans WHERE loan_id=?",
                         (loan_id,)).fetchone()
        return dict(row) if row else None


def create_loan(name: str, loan_type: str,
                 principal: float, interest_rate: float,
                 term_months: int, start_date: str,
                 bank: str | None = None,
                 monthly_payment: float | None = None,
                 due_day: int | None = None,
                 account_code: str | None = None,
                 notes: str | None = None) -> int:
    init_db()
    # 自動計 monthly_payment（如未提供）
    if monthly_payment is None and term_months > 0:
        monthly_payment = calc_monthly_payment(
            principal, interest_rate, term_months)
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO loans
              (name, loan_type, bank, principal, interest_rate,
               term_months, monthly_payment, start_date, due_day,
               account_code, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (name, loan_type, bank, principal, interest_rate,
              term_months, monthly_payment, start_date, due_day,
              account_code, notes))
        return cur.lastrowid


def update_loan(loan_id: int, **fields):
    init_db()
    if not fields:
        return
    allowed = {"name", "loan_type", "bank", "principal",
                "interest_rate", "term_months", "monthly_payment",
                "start_date", "due_day", "account_code", "status",
                "notes"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(v)
    if not sets:
        return
    params.append(loan_id)
    with _conn() as c:
        c.execute(
            f"UPDATE loans SET {', '.join(sets)} WHERE loan_id=?",
            params)


def delete_loan(loan_id: int):
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM loans WHERE loan_id=?", (loan_id,))


def calc_monthly_payment(principal: float, annual_rate: float,
                          term_months: int) -> float:
    """等額本息每月供款 (EMI):
    M = P × r × (1+r)^n / ((1+r)^n − 1)
    r = monthly rate, n = term in months
    """
    if term_months <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / term_months
    r = annual_rate / 12.0
    n = term_months
    return principal * r * ((1 + r) ** n) / (((1 + r) ** n) - 1)
