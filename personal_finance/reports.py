"""個人理財報表：account balance / budget vs actual / project tracking。"""
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from . import db


def current_period_month() -> str:
    """'YYYY-MM' 嘅當月 string"""
    return date.today().strftime("%Y-%m")


def current_period_year() -> str:
    return date.today().strftime("%Y")


# ============================================================
# Account Balances
# ============================================================
def account_balance(account_code: str,
                     as_of_date: str | None = None,
                     in_hkd: bool = True) -> float:
    """攞某個 account 嘅 balance（截至某日）。

    Args:
        in_hkd: True = 用 HKD equivalent（multi-currency entries 自動 convert）
                False = 用原幣值（適合單一 currency account）
    """
    acc = db.get_account(account_code)
    if not acc:
        return 0
    opening = float(acc.get("opening_balance") or 0)

    if in_hkd:
        # 用 fx_rate convert，每行乘 entry 嘅 fx_rate
        sql = """
            SELECT COALESCE(SUM(jl.debit * COALESCE(je.fx_rate, 1)), 0) AS total_dr,
                   COALESCE(SUM(jl.credit * COALESCE(je.fx_rate, 1)), 0) AS total_cr
            FROM journal_lines jl
            JOIN journal_entries je ON je.entry_id=jl.entry_id
            WHERE jl.account_code=?
        """
    else:
        sql = """
            SELECT COALESCE(SUM(jl.debit), 0) AS total_dr,
                   COALESCE(SUM(jl.credit), 0) AS total_cr
            FROM journal_lines jl
            JOIN journal_entries je ON je.entry_id=jl.entry_id
            WHERE jl.account_code=?
        """
    params = [account_code]
    if as_of_date:
        sql += " AND je.entry_date <= ?"
        params.append(as_of_date)

    from .db import _conn
    with _conn() as c:
        row = c.execute(sql, params).fetchone()
        total_dr = float(row["total_dr"] or 0)
        total_cr = float(row["total_cr"] or 0)

    if acc["account_type"] in ("asset", "expense"):
        return opening + total_dr - total_cr
    else:  # liability / income
        return opening + total_cr - total_dr


def all_account_balances(as_of_date: str | None = None) -> list[dict]:
    """每個 account 嘅 balance + type — 優化版單一 SQL query。

    舊版對每個 account 跑一條 query（N × round trip），
    雲端 PG 上會慢到 3 分鐘。
    新版用 LEFT JOIN 一次過攞晒所有 account 嘅 balance。
    """
    # 日期 filter 放喺 ON clause 而非 WHERE，
    # 確保無 entries 嘅 account 仍會出現（balance = opening）
    date_join = ""
    params = []
    if as_of_date:
        date_join = "AND je.entry_date <= ?"
        params.append(as_of_date)

    sql = f"""
        SELECT a.code, a.name, a.account_type, a.icon, a.color,
               a.currency, a.opening_balance, a.sort_order,
               COALESCE(SUM(jl.debit * COALESCE(je.fx_rate, 1)), 0)
                   AS total_dr,
               COALESCE(SUM(jl.credit * COALESCE(je.fx_rate, 1)), 0)
                   AS total_cr
        FROM accounts a
        LEFT JOIN journal_lines jl ON jl.account_code = a.code
        LEFT JOIN journal_entries je
            ON je.entry_id = jl.entry_id {date_join}
        WHERE a.is_active = 1
        GROUP BY a.code, a.name, a.account_type, a.icon, a.color,
                 a.currency, a.opening_balance, a.sort_order
        ORDER BY a.account_type, a.sort_order, a.name
    """

    from .db import _conn
    with _conn() as c:
        rows = c.execute(sql, params).fetchall()

    out = []
    for r in rows:
        opening = float(r["opening_balance"] or 0)
        total_dr = float(r["total_dr"] or 0)
        total_cr = float(r["total_cr"] or 0)
        if r["account_type"] in ("asset", "expense"):
            balance = opening + total_dr - total_cr
        else:  # liability / income
            balance = opening + total_cr - total_dr
        out.append({
            "code": r["code"],
            "name": r["name"],
            "account_type": r["account_type"],
            "icon": r["icon"],
            "color": r["color"],
            "currency": r["currency"],
            "opening_balance": opening,
            "sort_order": r["sort_order"] if "sort_order" in r else 0,
            "balance": balance,
        })
    return out


def net_worth(as_of_date: str | None = None) -> dict:
    """總資產 - 總負債 = 淨資產"""
    balances = all_account_balances(as_of_date)
    assets = sum(b["balance"] for b in balances if b["account_type"] == "asset")
    liab = sum(b["balance"] for b in balances if b["account_type"] == "liability")
    return {
        "assets": assets,
        "liabilities": liab,
        "net_worth": assets - liab,
    }


# ============================================================
# Spending by Category (Monthly P&L)
# ============================================================
def spending_by_category(start_date: str, end_date: str,
                          period: str | None = None) -> list[dict]:
    """指定日期範圍嘅 expense by category。

    Args:
        start_date / end_date: YYYY-MM-DD
        period: 用嚟揾 budget（'YYYY-MM' 格式）。如果係月度先有意義
    """
    # 注意：PG 嚴格，HAVING 內唔可以用 alias `amount`，要用完整 expression
    # 同時 GROUP BY 要包埋 SELECT 內所有非 aggregate 嘅欄位
    sql = """
        SELECT jl.account_code,
               a.name, a.icon, a.color,
               COALESCE(SUM((jl.debit - jl.credit) * COALESCE(je.fx_rate, 1)), 0) AS amount
        FROM journal_lines jl
        JOIN journal_entries je ON je.entry_id=jl.entry_id
        JOIN accounts a ON a.code=jl.account_code
        WHERE a.account_type='expense'
          AND je.entry_date BETWEEN ? AND ?
        GROUP BY jl.account_code, a.name, a.icon, a.color
        HAVING COALESCE(SUM((jl.debit - jl.credit)
                              * COALESCE(je.fx_rate, 1)), 0) > 0
        ORDER BY amount DESC
    """
    from .db import _conn
    with _conn() as c:
        rows = c.execute(sql, (start_date, end_date)).fetchall()

    # 揾 budget（只係月度有 budget）
    budgets = {}
    if period:
        budgets = {b["account_code"]: float(b["amount"])
                    for b in db.list_budgets(period=period)}

    out = []
    for r in rows:
        amt = float(r["amount"] or 0)
        budget = budgets.get(r["account_code"])
        pct = (amt / budget * 100) if budget else None
        out.append({
            "code": r["account_code"],
            "name": r["name"],
            "icon": r["icon"],
            "color": r["color"],
            "amount": amt,
            "budget": budget,
            "pct_used": pct,
        })
    return out


def category_spending(period: str | None = None) -> list[dict]:
    """某個月份各 expense category 嘅總支出（backward compat wrapper）。

    period 格式：'YYYY-MM' (default = 當月)
    """
    if not period:
        period = current_period_month()
    # YYYY-MM → start / end of that month
    year, month = int(period[:4]), int(period[5:7])
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end_year, end_month = year + 1, 1
    else:
        end_year, end_month = year, month + 1
    from datetime import date as _d, timedelta
    end = (_d(end_year, end_month, 1) - timedelta(days=1)).isoformat()
    return spending_by_category(start, end, period=period)


def budget_vs_actual(period: str | None = None) -> list[dict]:
    """所有有 budget 嘅 category，顯示 budget vs actual。

    包括有 budget 但今月未花嘅，同冇 budget 但有花嘅。
    """
    if not period:
        period = current_period_month()

    actual_map = {row["code"]: row for row in category_spending(period)}
    budget_list = db.list_budgets(period=period)
    out_by_code = {}

    # 先加 actual（包括無 budget 嘅）
    for code, row in actual_map.items():
        out_by_code[code] = row

    # 再加 budget（包括有 budget 但 actual=0）
    for b in budget_list:
        code = b["account_code"]
        if code not in out_by_code:
            acc = db.get_account(code)
            if acc:
                out_by_code[code] = {
                    "code": code, "name": acc["name"],
                    "icon": acc["icon"], "color": acc["color"],
                    "amount": 0, "budget": float(b["amount"]),
                    "pct_used": 0,
                }
            else:
                continue
        else:
            out_by_code[code]["budget"] = float(b["amount"])
            amt = out_by_code[code]["amount"]
            out_by_code[code]["pct_used"] = (
                amt / float(b["amount"]) * 100 if b["amount"] else None)

    # Sort: 超支嗰啲先，然後接近 budget 嘅
    def sort_key(x):
        if x.get("pct_used") is None:
            return (0, -x["amount"])  # 無 budget，按支出
        return (-1 if x["pct_used"] > 100 else 1, -x["pct_used"])

    return sorted(out_by_code.values(), key=sort_key)


# ============================================================
# Trend / Time Series
# ============================================================
def monthly_spending(months: int = 12) -> list[dict]:
    """過去 N 個月 total expense"""
    sql = """
        SELECT strftime('%Y-%m', je.entry_date) AS month,
               COALESCE(SUM(jl.debit - jl.credit), 0) AS amount
        FROM journal_lines jl
        JOIN journal_entries je ON je.entry_id=jl.entry_id
        JOIN accounts a ON a.code=jl.account_code
        WHERE a.account_type='expense'
        GROUP BY month
        ORDER BY month DESC
        LIMIT ?
    """
    from .db import _conn
    with _conn() as c:
        rows = c.execute(sql, (months,)).fetchall()
    return [{"month": r["month"], "amount": float(r["amount"] or 0)}
             for r in rows]


def category_monthly_trend(category_code: str,
                             months: int = 12) -> list[dict]:
    """單一 category 過去 N 個月 trend"""
    sql = """
        SELECT strftime('%Y-%m', je.entry_date) AS month,
               COALESCE(SUM(jl.debit - jl.credit), 0) AS amount
        FROM journal_lines jl
        JOIN journal_entries je ON je.entry_id=jl.entry_id
        WHERE jl.account_code=?
        GROUP BY month
        ORDER BY month DESC
        LIMIT ?
    """
    from .db import _conn
    with _conn() as c:
        rows = c.execute(sql, (category_code, months)).fetchall()
    return [{"month": r["month"], "amount": float(r["amount"] or 0)}
             for r in rows]


# ============================================================
# Project Tracking
# ============================================================
def project_spending(project_id: int) -> dict:
    """某個 project 嘅總支出 + budget vs actual"""
    proj = db.get_project(project_id)
    if not proj:
        return {}

    sql = """
        SELECT jl.account_code, a.name, a.icon,
               COALESCE(SUM(jl.debit - jl.credit), 0) AS amount
        FROM journal_lines jl
        JOIN journal_entries je ON je.entry_id=jl.entry_id
        JOIN accounts a ON a.code=jl.account_code
        WHERE je.project_id=? AND a.account_type='expense'
        GROUP BY jl.account_code, a.name, a.icon
        ORDER BY amount DESC
    """
    from .db import _conn
    with _conn() as c:
        rows = c.execute(sql, (project_id,)).fetchall()

    by_category = [
        {"code": r["account_code"], "name": r["name"], "icon": r["icon"],
         "amount": float(r["amount"] or 0)}
        for r in rows
    ]
    total = sum(c["amount"] for c in by_category)
    budget = float(proj.get("total_budget") or 0)

    return {
        "project": proj,
        "by_category": by_category,
        "total_spent": total,
        "budget": budget,
        "remaining": budget - total if budget else None,
        "pct_used": (total / budget * 100) if budget else None,
    }


# ============================================================
# Forecast 下個月
# ============================================================
def forecast_next_month() -> dict:
    """簡單 forecast：用過去 3 個月平均"""
    recent = monthly_spending(months=3)
    if not recent:
        return {"forecast": 0, "based_on": []}
    avg = sum(m["amount"] for m in recent) / len(recent)
    return {"forecast": avg, "based_on": recent}


# ============================================================
# Period 計算 helpers
# ============================================================
def period_dates(period_type: str) -> tuple[str, str]:
    """攞 period type 對應嘅 start/end date.

    period_type:
        'this_month' / 'last_month' / 'this_year' / 'last_year' / 'ytd' / 'all'
    Returns: (start_date, end_date) ISO format
    """
    today = date.today()
    if period_type == "this_month":
        start = today.replace(day=1)
        return (start.isoformat(), today.isoformat())
    elif period_type == "last_month":
        first_this = today.replace(day=1)
        last_prev = first_this.replace(day=1)
        # Go back one day
        from datetime import timedelta
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
        return (start.isoformat(), end.isoformat())
    elif period_type == "this_year" or period_type == "ytd":
        start = date(today.year, 1, 1)
        return (start.isoformat(), today.isoformat())
    elif period_type == "last_year":
        start = date(today.year - 1, 1, 1)
        end = date(today.year - 1, 12, 31)
        return (start.isoformat(), end.isoformat())
    elif period_type == "all":
        return ("1900-01-01", "9999-12-31")
    else:
        raise ValueError(f"Unknown period type: {period_type}")


def period_label(period_type: str) -> str:
    """人類可讀 label"""
    return {
        "this_month": "本月", "last_month": "上月",
        "this_year": "本年", "ytd": "年初至今",
        "last_year": "上年", "all": "全部",
    }.get(period_type, period_type)


# ============================================================
# Income Statement (P&L)
# ============================================================
def income_statement(start_date: str, end_date: str) -> dict:
    """收支表 - 計指定 period 嘅 income 同 expense.

    Returns:
        {
            "income": [(code, name, amount), ...],
            "expense": [(code, name, amount), ...],
            "total_income": float,
            "total_expense": float,
            "net": float,
            "period": (start, end),
        }
    """
    from .db import _conn
    init_db = db.init_db
    init_db()

    # ⚠️ 必須用 INNER JOIN — 之前用 LEFT JOIN 加 date filter 喺 ON clause
    # 會錯誤包含舊期 entries（因為 jl 行被保留即使 je date 唔 match）
    # PG 嚴格：HAVING 用 expression、GROUP BY 包埋所有 SELECT 非 aggregate
    sql = """
        SELECT a.code, a.name, a.account_type, a.icon,
               COALESCE(SUM(jl.debit * COALESCE(je.fx_rate, 1)), 0) AS total_dr,
               COALESCE(SUM(jl.credit * COALESCE(je.fx_rate, 1)), 0) AS total_cr
        FROM accounts a
        INNER JOIN journal_lines jl ON jl.account_code=a.code
        INNER JOIN journal_entries je ON je.entry_id=jl.entry_id
        WHERE a.account_type IN ('income', 'expense')
          AND je.entry_date BETWEEN ? AND ?
        GROUP BY a.code, a.name, a.account_type, a.icon
        HAVING COALESCE(SUM(jl.debit * COALESCE(je.fx_rate, 1)), 0) > 0
            OR COALESCE(SUM(jl.credit * COALESCE(je.fx_rate, 1)), 0) > 0
        ORDER BY a.account_type DESC,
                 COALESCE(SUM(jl.credit * COALESCE(je.fx_rate, 1)), 0)
                 - COALESCE(SUM(jl.debit * COALESCE(je.fx_rate, 1)), 0) DESC
    """
    with _conn() as c:
        rows = c.execute(sql, (start_date, end_date)).fetchall()

    income = []
    expense = []
    for r in rows:
        dr = float(r["total_dr"] or 0)
        cr = float(r["total_cr"] or 0)
        if r["account_type"] == "income":
            amount = cr - dr  # income normal balance = credit
            if amount != 0:
                income.append({
                    "code": r["code"], "name": r["name"],
                    "icon": r["icon"], "amount": amount,
                })
        else:  # expense
            amount = dr - cr  # expense normal balance = debit
            if amount != 0:
                expense.append({
                    "code": r["code"], "name": r["name"],
                    "icon": r["icon"], "amount": amount,
                })

    total_income = sum(i["amount"] for i in income)
    total_expense = sum(e["amount"] for e in expense)
    return {
        "income": income,
        "expense": expense,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": total_income - total_expense,
        "period": (start_date, end_date),
    }


# ============================================================
# Balance Sheet
# ============================================================
def balance_sheet(as_of_date: str | None = None) -> dict:
    """資產負債表 - 截至某日.

    Returns:
        {
            "assets": [(code, name, balance), ...],
            "liabilities": [(code, name, balance), ...],
            "total_assets": float,
            "total_liabilities": float,
            "net_worth": float,
            "as_of": str,
        }
    """
    if not as_of_date:
        as_of_date = date.today().isoformat()

    assets = []
    liabs = []
    for a in db.list_accounts(active_only=True):
        if a["account_type"] not in ("asset", "liability"):
            continue
        bal = account_balance(a["code"], as_of_date=as_of_date, in_hkd=True)
        if abs(bal) < 0.005:
            continue  # skip zero balance
        item = {
            "code": a["code"], "name": a["name"],
            "icon": a["icon"], "balance": bal,
        }
        if a["account_type"] == "asset":
            assets.append(item)
        else:
            liabs.append(item)

    # Sort by balance desc
    assets.sort(key=lambda x: -x["balance"])
    liabs.sort(key=lambda x: -x["balance"])

    total_assets = sum(a["balance"] for a in assets)
    total_liabs = sum(l["balance"] for l in liabs)
    return {
        "assets": assets,
        "liabilities": liabs,
        "total_assets": total_assets,
        "total_liabilities": total_liabs,
        "net_worth": total_assets - total_liabs,
        "as_of": as_of_date,
    }


# ============================================================
# Period Compare（今期 vs 上期）
# ============================================================
def period_compare(period_a: str = "this_month",
                    period_b: str = "last_month") -> dict:
    """並排比較 2 個 period.

    Returns:
        {
            "period_a_label": str, "period_b_label": str,
            "income_a": float, "income_b": float, "income_diff": float,
            "expense_a": float, "expense_b": float, "expense_diff": float,
            "net_a": float, "net_b": float, "net_diff": float,
            "categories": [{code, name, amount_a, amount_b, diff, pct_change}],
        }
    """
    sa, ea = period_dates(period_a)
    sb, eb = period_dates(period_b)

    is_a = income_statement(sa, ea)
    is_b = income_statement(sb, eb)

    # Combine expense categories
    exp_a = {e["code"]: e for e in is_a["expense"]}
    exp_b = {e["code"]: e for e in is_b["expense"]}
    all_codes = set(exp_a.keys()) | set(exp_b.keys())
    cats = []
    for code in all_codes:
        a_data = exp_a.get(code)
        b_data = exp_b.get(code)
        sample = a_data or b_data
        amount_a = a_data["amount"] if a_data else 0
        amount_b = b_data["amount"] if b_data else 0
        diff = amount_a - amount_b
        pct = (diff / amount_b * 100) if amount_b else (None if amount_a == 0 else float("inf"))
        cats.append({
            "code": code, "name": sample["name"], "icon": sample["icon"],
            "amount_a": amount_a, "amount_b": amount_b,
            "diff": diff, "pct_change": pct,
        })
    # Sort by amount_a desc
    cats.sort(key=lambda x: -x["amount_a"])

    return {
        "period_a_label": period_label(period_a),
        "period_b_label": period_label(period_b),
        "income_a": is_a["total_income"], "income_b": is_b["total_income"],
        "income_diff": is_a["total_income"] - is_b["total_income"],
        "expense_a": is_a["total_expense"], "expense_b": is_b["total_expense"],
        "expense_diff": is_a["total_expense"] - is_b["total_expense"],
        "net_a": is_a["net"], "net_b": is_b["net"],
        "net_diff": is_a["net"] - is_b["net"],
        "categories": cats,
    }
