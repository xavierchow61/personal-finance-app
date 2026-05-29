"""Cached wrappers around personal_finance.reports / database calls.

每個 wrapper 用 st.cache_data 加 60 秒 TTL：
- 首次 call：跑 PG query（3-5s）
- 60 秒內再 call：直接從 memory 攞，<10ms
- TTL 過後或數據變動：重新 query

寫入操作（add/edit/delete）後請 call invalidate_all()
清 cache，確保即時見到最新數據。
"""
from __future__ import annotations
import streamlit as st

from personal_finance import reports as pfr
import database as invdb


# === Personal Finance Reports ===

@st.cache_data(ttl=60, show_spinner=False)
def net_worth(as_of_date=None):
    return pfr.net_worth(as_of_date)


@st.cache_data(ttl=60, show_spinner=False)
def income_statement(start_date, end_date):
    return pfr.income_statement(start_date, end_date)


@st.cache_data(ttl=60, show_spinner=False)
def all_account_balances(as_of_date=None):
    return pfr.all_account_balances(as_of_date)


@st.cache_data(ttl=60, show_spinner=False)
def spending_by_category(start_date, end_date, period=None):
    return pfr.spending_by_category(start_date, end_date, period)


@st.cache_data(ttl=60, show_spinner=False)
def monthly_spending(months=12):
    return pfr.monthly_spending(months)


@st.cache_data(ttl=60, show_spinner=False)
def budget_vs_actual(period=None):
    return pfr.budget_vs_actual(period)


@st.cache_data(ttl=60, show_spinner=False)
def balance_sheet(as_of_date=None):
    return pfr.balance_sheet(as_of_date)


@st.cache_data(ttl=60, show_spinner=False)
def period_compare(period_a, period_b):
    return pfr.period_compare(period_a, period_b)


@st.cache_data(ttl=60, show_spinner=False)
def account_balance(account_code, as_of_date=None, in_hkd=True):
    return pfr.account_balance(account_code, as_of_date, in_hkd)


# === Invoices ===

@st.cache_data(ttl=60, show_spinner=False)
def invoices_list_all():
    return invdb.list_all()


@st.cache_data(ttl=60, show_spinner=False)
def invoices_top_n_by_amount(n=5):
    return invdb.top_n_by_amount(n)


@st.cache_data(ttl=60, show_spinner=False)
def invoices_reimbursement_summary():
    return invdb.reimbursement_summary()


@st.cache_data(ttl=60, show_spinner=False)
def invoices_by_expense_type(expense_type):
    return invdb.by_expense_type(expense_type)


# === Period dates (cheap but cache anyway 因為頻繁 call）===

@st.cache_data(ttl=60, show_spinner=False)
def period_dates(period_type):
    return pfr.period_dates(period_type)


# ============================================================
# CACHE INVALIDATION
# ============================================================

def invalidate_all():
    """清空所有 cached PG 數據。
    寫入操作（add invoice / edit / delete）後 call。
    """
    st.cache_data.clear()


def invalidate_invoices():
    """只清 invoice 相關 cache（如只改 invoice）"""
    invoices_list_all.clear()
    invoices_top_n_by_amount.clear()
    invoices_reimbursement_summary.clear()
    invoices_by_expense_type.clear()
    # 但分錄變動會影響餘額，仍然清埋
    net_worth.clear()
    all_account_balances.clear()
    income_statement.clear()
    spending_by_category.clear()


# ============================================================
# 🚀 並行 fetch + bundle cache（首頁專用）
# 將 5 個 query 並行跑（ThreadPoolExecutor），由 ~25s sequential
# 降到 ~5s。再加 cache，60s 內 reload 秒回。
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_dashboard_bundle(as_of_date, start_date, end_date):
    """並行 fetch 首頁所有 data。Return dict with 5 keys."""
    from concurrent.futures import ThreadPoolExecutor

    def safe(fn, *args, default=None):
        try:
            return fn(*args)
        except Exception as ex:
            print(f"[bundle] {fn.__name__} failed: {ex}")
            return default

    with ThreadPoolExecutor(max_workers=5) as ex:
        f_nw = ex.submit(safe, pfr.net_worth, as_of_date,
                          default={"assets": 0, "liabilities": 0,
                                    "net_worth": 0})
        f_pl = ex.submit(safe, pfr.income_statement,
                          start_date, end_date,
                          default={"total_expense": 0,
                                    "total_income": 0,
                                    "net": 0, "income": [],
                                    "expense": []})
        f_cats = ex.submit(safe, pfr.spending_by_category,
                            start_date, end_date, default=[])
        f_top = ex.submit(safe, invdb.top_n_by_amount, 5, default=[])
        f_bal = ex.submit(safe, pfr.all_account_balances,
                           as_of_date, default=[])

    return {
        "net_worth": f_nw.result(),
        "income_statement": f_pl.result(),
        "spending_by_category": f_cats.result(),
        "top_invoices": f_top.result(),
        "all_balances": f_bal.result(),
    }


# ============================================================
# 個人記賬頁 bundle
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_ledger_bundle():
    """並行 fetch 個人記賬頁所有 data"""
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except Exception as ex:
            print(f"[ledger] {fn.__name__} failed: {ex}")
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_entries = ex.submit(safe, pfdb.list_entries, None, None,
                               None, None, None, 100)
        f_accs = ex.submit(safe, pfdb.list_accounts, False)
        f_balances = ex.submit(safe, pfr.all_account_balances, None)

    return {
        "entries": f_entries.result(),
        "accounts": f_accs.result(),
        "balances": f_balances.result(),
    }


# ============================================================
# 預算頁 bundle
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_budget_bundle(period):
    """並行 fetch 預算頁所有 data"""
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except Exception as ex:
            print(f"[budget] {fn.__name__} failed: {ex}")
            return []

    with ThreadPoolExecutor(max_workers=4) as ex:
        f_rows = ex.submit(safe, pfr.budget_vs_actual, period)
        f_trend = ex.submit(safe, pfr.monthly_spending, 12)
        f_cats = ex.submit(safe, pfdb.list_accounts, True, "expense")
        f_budgets = ex.submit(safe, pfdb.list_budgets, period)

    return {
        "rows": f_rows.result(),
        "trend": f_trend.result(),
        "expense_categories": f_cats.result(),
        "existing_budgets": f_budgets.result(),
    }


# ============================================================
# 報銷追蹤頁 bundle
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def fetch_reimbursement_bundle():
    """並行 fetch 報銷追蹤頁所有 data"""
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, default=None, **kw):
        try:
            return fn(*args, **kw)
        except Exception:
            return default

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_summary = ex.submit(safe, invdb.reimbursement_summary,
                               default={})
        f_company = ex.submit(safe, invdb.by_expense_type,
                               "公司報銷", default=[])
        f_assets = ex.submit(safe, pfdb.list_accounts, True, "asset",
                              default=[])

    return {
        "summary": f_summary.result(),
        "company_invoices": f_company.result(),
        "asset_accounts": f_assets.result(),
    }


@st.cache_data(ttl=60, show_spinner=False)
def fetch_credit_cards_bundle():
    """並行 fetch 信用卡 dashboard data"""
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, default=None):
        try:
            return fn(*args)
        except Exception:
            return default

    cards = safe(pfdb.list_credit_cards, default=[])
    cards_with_limit = [c for c in cards
                         if (c.get("credit_limit") or 0) > 0]
    if not cards_with_limit:
        return {"cards": [], "balances": {}}

    # 並行攞每張卡 balance
    with ThreadPoolExecutor(max_workers=min(8, len(cards_with_limit))) as ex:
        futures = {
            c["account_code"]:
            ex.submit(safe, pfr.account_balance,
                      c["account_code"], None, True, default=0)
            for c in cards_with_limit
        }
        balances = {code: f.result() for code, f in futures.items()}

    return {"cards": cards_with_limit, "balances": balances}
