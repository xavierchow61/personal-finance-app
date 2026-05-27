"""Personal Finance database schemas + CRUD。

存喺 `personal_finance.db`（同 invoices.db 分開，避免污染現有資料）。
"""
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from config import BASE_DIR, get_personal_finance_db_path


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

-- ============ JOURNAL ENTRIES ============
CREATE TABLE IF NOT EXISTS journal_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    description TEXT,
    invoice_id INTEGER,                        -- link to invoices.db invoices.id
    project_id INTEGER,                        -- optional
    notes TEXT,
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

-- ============ PROJECTS ============
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
"""


@contextmanager
def _conn():
    # 動態取目前用戶嘅 DB；無登入則跌回 BASE_DIR/personal_finance.db
    db_path = get_personal_finance_db_path()
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)
        # Migration：journal_entries 加 currency / fx_rate / hkd_amount
        cols = {r["name"] for r in c.execute(
            "PRAGMA table_info(journal_entries)").fetchall()}
        if "currency" not in cols:
            c.execute("ALTER TABLE journal_entries ADD COLUMN currency TEXT DEFAULT 'HKD'")
        if "fx_rate" not in cols:
            c.execute("ALTER TABLE journal_entries ADD COLUMN fx_rate REAL DEFAULT 1.0")


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
    init_db()
    sql = """
        SELECT DISTINCT je.*,
               (SELECT GROUP_CONCAT(jl.account_code || ':' ||
                                     CASE WHEN jl.debit > 0
                                          THEN 'Dr ' || jl.debit
                                          ELSE 'Cr ' || jl.credit END,
                                     ' | ')
                FROM journal_lines jl WHERE jl.entry_id=je.entry_id) AS lines_summary,
               (SELECT MAX(jl.debit + jl.credit)
                FROM journal_lines jl WHERE jl.entry_id=je.entry_id) AS amount
        FROM journal_entries je
        LEFT JOIN journal_lines jl ON jl.entry_id=je.entry_id
        WHERE 1=1
    """
    params = []
    if start_date:
        sql += " AND je.entry_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND je.entry_date <= ?"
        params.append(end_date)
    if account_code:
        sql += " AND jl.account_code = ?"
        params.append(account_code)
    if project_id is not None:
        sql += " AND je.project_id = ?"
        params.append(project_id)
    if invoice_id is not None:
        sql += " AND je.invoice_id = ?"
        params.append(invoice_id)
    sql += " ORDER BY je.entry_date DESC, je.entry_id DESC"
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
