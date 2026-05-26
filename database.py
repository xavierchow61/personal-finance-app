"""SQLite 儲存所有提取出嘅單據"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import DB_PATH


# === 報銷類型 ===
EXPENSE_TYPES = ["私人", "公司報銷", "可扣稅"]


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_date TEXT,
    store_name TEXT,
    category TEXT,
    total_amount REAL,
    currency TEXT,
    payment_method TEXT,
    items_json TEXT,
    tax REAL,
    receipt_number TEXT,
    notes TEXT,
    source_file TEXT,
    extracted_at TEXT,
    expense_type TEXT DEFAULT '私人',
    reimbursed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_purchase_date ON invoices(purchase_date)",
    "CREATE INDEX IF NOT EXISTS idx_category ON invoices(category)",
    "CREATE INDEX IF NOT EXISTS idx_total_amount ON invoices(total_amount)",
    "CREATE INDEX IF NOT EXISTS idx_expense_type ON invoices(expense_type)",
]


@contextmanager
def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        # 1. 確保 table 存在（舊版可能冇新 column）
        con.execute(CREATE_TABLE)
        # 2. Migration: 補返新 column 入舊 DB（必須喺 index 之前）
        cols = {r["name"] for r in con.execute("PRAGMA table_info(invoices)").fetchall()}
        if "expense_type" not in cols:
            con.execute("ALTER TABLE invoices ADD COLUMN expense_type TEXT DEFAULT '私人'")
        if "reimbursed" not in cols:
            con.execute("ALTER TABLE invoices ADD COLUMN reimbursed INTEGER DEFAULT 0")
        # 3. 而家先建 index
        for sql in INDEXES:
            con.execute(sql)


def save_invoice(data: dict) -> int:
    """儲存一張單，返回 id。會偵測重複（同檔案 / 同日期+商店+金額）"""
    init_db()
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO invoices
               (purchase_date, store_name, category, total_amount, currency,
                payment_method, items_json, tax, receipt_number, notes,
                source_file, extracted_at, expense_type, reimbursed)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("purchase_date"),
                data.get("store_name"),
                data.get("category"),
                data.get("total_amount") or 0.0,
                data.get("currency"),
                data.get("payment_method"),
                json.dumps(data.get("items") or [], ensure_ascii=False),
                data.get("tax"),
                data.get("receipt_number"),
                data.get("notes"),
                data.get("source_file"),
                data.get("extracted_at") or datetime.now().isoformat(timespec="seconds"),
                data.get("expense_type") or "私人",
                1 if data.get("reimbursed") else 0,
            ),
        )
        return cur.lastrowid


def is_duplicate(data: dict) -> dict | None:
    """偵測重複單據：同檔案路徑 OR 同 (日期+商店+金額)。返回已存在嗰張嘅 dict，冇就 None"""
    init_db()
    with _conn() as con:
        # 1. 同 source_file
        if data.get("source_file"):
            row = con.execute(
                "SELECT * FROM invoices WHERE source_file=? LIMIT 1",
                (data["source_file"],),
            ).fetchone()
            if row:
                return _row_to_dict(row)
        # 2. 同 (date + store + amount)
        if data.get("purchase_date") and data.get("store_name") and data.get("total_amount"):
            row = con.execute(
                """SELECT * FROM invoices
                   WHERE purchase_date=? AND store_name=? AND total_amount=?
                   LIMIT 1""",
                (data["purchase_date"], data["store_name"], data["total_amount"]),
            ).fetchone()
            if row:
                return _row_to_dict(row)
    return None


def update_invoice(invoice_id: int, data: dict):
    """更新一張單"""
    init_db()
    with _conn() as con:
        con.execute(
            """UPDATE invoices SET
                 purchase_date=?, store_name=?, category=?, total_amount=?,
                 currency=?, payment_method=?, items_json=?, tax=?,
                 receipt_number=?, notes=?, expense_type=?, reimbursed=?
               WHERE id=?""",
            (
                data.get("purchase_date"),
                data.get("store_name"),
                data.get("category"),
                data.get("total_amount") or 0.0,
                data.get("currency"),
                data.get("payment_method"),
                json.dumps(data.get("items") or [], ensure_ascii=False),
                data.get("tax"),
                data.get("receipt_number"),
                data.get("notes"),
                data.get("expense_type") or "私人",
                1 if data.get("reimbursed") else 0,
                invoice_id,
            ),
        )


def toggle_reimbursed(invoice_id: int) -> bool:
    """切換報銷狀態，返回新狀態（True = 已報銷）"""
    init_db()
    with _conn() as con:
        row = con.execute("SELECT reimbursed FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not row:
            return False
        new = 0 if row["reimbursed"] else 1
        con.execute("UPDATE invoices SET reimbursed=? WHERE id=?", (new, invoice_id))
        return bool(new)


def delete_invoice(invoice_id: int):
    init_db()
    with _conn() as con:
        con.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))


def list_all(order_by: str = "purchase_date DESC, id DESC") -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(f"SELECT * FROM invoices ORDER BY {order_by}").fetchall()
        return [_row_to_dict(r) for r in rows]


def get_invoice(invoice_id: int) -> dict | None:
    init_db()
    with _conn() as con:
        row = con.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        return _row_to_dict(row) if row else None


def top_n_by_amount(n: int = 5) -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM invoices ORDER BY total_amount DESC LIMIT ?", (n,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def top_n_categories(n: int = 5) -> list[tuple[str, float]]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            """SELECT category, SUM(total_amount) AS total
               FROM invoices
               WHERE category IS NOT NULL
               GROUP BY category
               ORDER BY total DESC
               LIMIT ?""",
            (n,),
        ).fetchall()
        return [(r["category"], float(r["total"] or 0)) for r in rows]


def category_totals() -> list[tuple[str, float]]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            """SELECT COALESCE(category, '其他') AS category,
                      SUM(total_amount) AS total
               FROM invoices
               GROUP BY category
               ORDER BY total DESC"""
        ).fetchall()
        return [(r["category"], float(r["total"] or 0)) for r in rows]


def grand_total() -> float:
    init_db()
    with _conn() as con:
        row = con.execute("SELECT SUM(total_amount) AS t FROM invoices").fetchone()
        return float(row["t"] or 0)


def count() -> int:
    init_db()
    with _conn() as con:
        row = con.execute("SELECT COUNT(*) AS c FROM invoices").fetchone()
        return int(row["c"])


# === 報銷相關 ===
def by_expense_type(expense_type: str) -> list[dict]:
    init_db()
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM invoices WHERE expense_type=? ORDER BY purchase_date DESC",
            (expense_type,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def reimbursement_summary() -> dict:
    """報銷統計：返回 {company_total, company_reimbursed, company_pending,
                       tax_deductible_total, personal_total}"""
    init_db()
    with _conn() as con:
        company = con.execute(
            "SELECT SUM(total_amount) AS t FROM invoices WHERE expense_type='公司報銷'"
        ).fetchone()
        company_reimbursed = con.execute(
            "SELECT SUM(total_amount) AS t FROM invoices WHERE expense_type='公司報銷' AND reimbursed=1"
        ).fetchone()
        tax = con.execute(
            "SELECT SUM(total_amount) AS t FROM invoices WHERE expense_type='可扣稅'"
        ).fetchone()
        personal = con.execute(
            "SELECT SUM(total_amount) AS t FROM invoices WHERE expense_type='私人' OR expense_type IS NULL"
        ).fetchone()
        c_total = float(company["t"] or 0)
        c_done = float(company_reimbursed["t"] or 0)
        return {
            "company_total": c_total,
            "company_reimbursed": c_done,
            "company_pending": c_total - c_done,
            "tax_deductible_total": float(tax["t"] or 0),
            "personal_total": float(personal["t"] or 0),
        }


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("items_json"):
        try:
            d["items"] = json.loads(d["items_json"])
        except json.JSONDecodeError:
            d["items"] = []
    else:
        d["items"] = []
    # Boolean
    d["reimbursed"] = bool(d.get("reimbursed"))
    # Default expense_type
    if not d.get("expense_type"):
        d["expense_type"] = "私人"
    return d
