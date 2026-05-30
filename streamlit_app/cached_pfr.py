"""Cached wrappers around personal_finance.reports / database calls.

🔒 多用戶安全：每個 cached function 嘅 key 都包 user_id，
避免兩個用戶喺同一個 Python process 共享 cache。

設計：用戶呼叫 cpfr.foo(...) → 內部 wrapper 抽 user_id →
傳畀 _foo_impl(user_id, ...)。`_user_id` 係 cache key 一部分但
唔影響 impl 邏輯（schema 已由 DB layer 隔離）。

寫入操作後請呼叫 invalidate_all() 清快取。

ThreadPoolExecutor 注意：worker thread 冇 ScriptRunContext，
要喺 submit 前抽 user_id，喺 worker 第一行呼叫
db_backend.set_thread_user_id(uid) 讓 _conn() 識別當前用戶。
"""
from __future__ import annotations
import streamlit as st

from personal_finance import reports as pfr
import database as invdb
from db_backend import set_thread_user_id


# ============================================================
# 取得當前用戶 id（做 cache key）
# ============================================================
def _uid() -> str:
    """攞 cache key 用嘅 user id。未 login → 'anon'。"""
    try:
        user = st.session_state.get("auth_user")
        if not user:
            return "anon"
        if isinstance(user, dict):
            return user.get("id") or user.get("email") or "anon"
        return str(user)
    except Exception:
        return "anon"


# ============================================================
# IMPL functions — _user_id 係 cache key（唔影響邏輯，
# 因為 schema 已喺 DB layer 隔離）
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def _list_accounts_impl(_user_id, active_only=True, account_type=None):
    from personal_finance import db as pfdb
    return pfdb.list_accounts(
        active_only=active_only, account_type=account_type)


@st.cache_data(ttl=60, show_spinner=False)
def _list_payment_aliases_impl(_user_id):
    from personal_finance import db as pfdb
    return pfdb.list_payment_aliases()


@st.cache_data(ttl=60, show_spinner=False)
def _list_credit_cards_impl(_user_id):
    from personal_finance import db as pfdb
    return pfdb.list_credit_cards()


@st.cache_data(ttl=60, show_spinner=False)
def _list_fx_rates_impl(_user_id):
    from personal_finance import db as pfdb
    return pfdb.list_fx_rates() if hasattr(pfdb, 'list_fx_rates') else []


@st.cache_data(ttl=60, show_spinner=False)
def _list_projects_impl(_user_id):
    from personal_finance import db as pfdb
    return pfdb.list_projects() if hasattr(pfdb, 'list_projects') else []


@st.cache_data(ttl=60, show_spinner=False)
def _list_closed_periods_impl(_user_id):
    from personal_finance import db as pfdb
    return (pfdb.list_closed_periods()
            if hasattr(pfdb, 'list_closed_periods') else [])


@st.cache_data(ttl=60, show_spinner=False)
def _net_worth_impl(_user_id, as_of_date=None):
    return pfr.net_worth(as_of_date)


@st.cache_data(ttl=60, show_spinner=False)
def _income_statement_impl(_user_id, start_date, end_date):
    return pfr.income_statement(start_date, end_date)


@st.cache_data(ttl=60, show_spinner=False)
def _all_account_balances_impl(_user_id, as_of_date=None):
    return pfr.all_account_balances(as_of_date)


@st.cache_data(ttl=60, show_spinner=False)
def _spending_by_category_impl(_user_id, start_date, end_date, period=None):
    return pfr.spending_by_category(start_date, end_date, period)


@st.cache_data(ttl=60, show_spinner=False)
def _monthly_spending_impl(_user_id, months=12):
    return pfr.monthly_spending(months)


@st.cache_data(ttl=60, show_spinner=False)
def _budget_vs_actual_impl(_user_id, period=None):
    return pfr.budget_vs_actual(period)


@st.cache_data(ttl=60, show_spinner=False)
def _balance_sheet_impl(_user_id, as_of_date=None):
    return pfr.balance_sheet(as_of_date)


@st.cache_data(ttl=60, show_spinner=False)
def _period_compare_impl(_user_id, period_a, period_b):
    return pfr.period_compare(period_a, period_b)


@st.cache_data(ttl=60, show_spinner=False)
def _account_balance_impl(_user_id, account_code, as_of_date=None,
                          in_hkd=True):
    return pfr.account_balance(account_code, as_of_date, in_hkd)


@st.cache_data(ttl=60, show_spinner=False)
def _invoices_list_all_impl(_user_id):
    return invdb.list_all()


@st.cache_data(ttl=60, show_spinner=False)
def _invoices_top_n_by_amount_impl(_user_id, n=5):
    return invdb.top_n_by_amount(n)


@st.cache_data(ttl=60, show_spinner=False)
def _invoices_reimbursement_summary_impl(_user_id):
    return invdb.reimbursement_summary()


@st.cache_data(ttl=60, show_spinner=False)
def _invoices_by_expense_type_impl(_user_id, expense_type):
    return invdb.by_expense_type(expense_type)


# period_dates 係純計算（無 DB query），冇 user 概念
@st.cache_data(ttl=60, show_spinner=False)
def period_dates(period_type):
    return pfr.period_dates(period_type)


# ============================================================
# 對外 API — 用戶呼叫呢啲，內部自動注入 user_id
# ============================================================

def list_accounts(active_only=True, account_type=None):
    return _list_accounts_impl(_uid(), active_only, account_type)


def list_payment_aliases():
    return _list_payment_aliases_impl(_uid())


def list_credit_cards():
    return _list_credit_cards_impl(_uid())


def list_fx_rates():
    return _list_fx_rates_impl(_uid())


def list_projects():
    return _list_projects_impl(_uid())


def list_closed_periods():
    return _list_closed_periods_impl(_uid())


def net_worth(as_of_date=None):
    return _net_worth_impl(_uid(), as_of_date)


def income_statement(start_date, end_date):
    return _income_statement_impl(_uid(), start_date, end_date)


def all_account_balances(as_of_date=None):
    return _all_account_balances_impl(_uid(), as_of_date)


def spending_by_category(start_date, end_date, period=None):
    return _spending_by_category_impl(_uid(), start_date, end_date, period)


def monthly_spending(months=12):
    return _monthly_spending_impl(_uid(), months)


def budget_vs_actual(period=None):
    return _budget_vs_actual_impl(_uid(), period)


def balance_sheet(as_of_date=None):
    return _balance_sheet_impl(_uid(), as_of_date)


def period_compare(period_a, period_b):
    return _period_compare_impl(_uid(), period_a, period_b)


def account_balance(account_code, as_of_date=None, in_hkd=True):
    return _account_balance_impl(_uid(), account_code, as_of_date, in_hkd)


def invoices_list_all():
    return _invoices_list_all_impl(_uid())


def invoices_top_n_by_amount(n=5):
    return _invoices_top_n_by_amount_impl(_uid(), n)


def invoices_reimbursement_summary():
    return _invoices_reimbursement_summary_impl(_uid())


def invoices_by_expense_type(expense_type):
    return _invoices_by_expense_type_impl(_uid(), expense_type)


# ============================================================
# CACHE INVALIDATION
# ============================================================

def invalidate_all():
    """清空所有 cached PG 數據。寫入後呼叫。"""
    st.cache_data.clear()


def invalidate_invoices():
    """只清 invoice 相關 cache"""
    _invoices_list_all_impl.clear()
    _invoices_top_n_by_amount_impl.clear()
    _invoices_reimbursement_summary_impl.clear()
    _invoices_by_expense_type_impl.clear()
    # 分錄變動會影響餘額
    _net_worth_impl.clear()
    _all_account_balances_impl.clear()
    _income_statement_impl.clear()
    _spending_by_category_impl.clear()


# ============================================================
# 🚀 並行 fetch + bundle cache（用 ThreadPoolExecutor）
#
# 🔒 重要：worker thread 冇 ScriptRunContext，
# 攞唔到 st.session_state.auth_user → DB 會 raise。
# 解決：submit 前抽 uid，每個 worker 第一行 set_thread_user_id(uid)
# ============================================================

def _make_safe_worker(fn, uid):
    """包一個 fn 喺 worker 入面執行：先 set thread user id 再 call"""
    def worker(*args, **kw):
        set_thread_user_id(uid)
        try:
            return fn(*args, **kw)
        finally:
            set_thread_user_id(None)
    return worker


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_dashboard_bundle_impl(_user_id, as_of_date, start_date, end_date):
    from concurrent.futures import ThreadPoolExecutor

    def safe(fn, *args, default=None):
        try:
            return fn(*args)
        except Exception as ex:
            print(f"[bundle] {fn.__name__} failed: {ex}")
            return default

    # Worker 包裝：自動設 thread-local user_id
    worker_safe = _make_safe_worker(safe, _user_id)

    with ThreadPoolExecutor(max_workers=5) as ex:
        f_nw = ex.submit(worker_safe, pfr.net_worth, as_of_date,
                          default={"assets": 0, "liabilities": 0,
                                    "net_worth": 0})
        f_pl = ex.submit(worker_safe, pfr.income_statement,
                          start_date, end_date,
                          default={"total_expense": 0,
                                    "total_income": 0,
                                    "net": 0, "income": [],
                                    "expense": []})
        f_cats = ex.submit(worker_safe, pfr.spending_by_category,
                            start_date, end_date, default=[])
        f_top = ex.submit(worker_safe, invdb.top_n_by_amount, 5,
                           default=[])
        f_bal = ex.submit(worker_safe, pfr.all_account_balances,
                           as_of_date, default=[])

    return {
        "net_worth": f_nw.result(),
        "income_statement": f_pl.result(),
        "spending_by_category": f_cats.result(),
        "top_invoices": f_top.result(),
        "all_balances": f_bal.result(),
    }


def fetch_dashboard_bundle(as_of_date, start_date, end_date):
    return _fetch_dashboard_bundle_impl(
        _uid(), as_of_date, start_date, end_date)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_ledger_bundle_impl(_user_id):
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except Exception as ex:
            print(f"[ledger] {fn.__name__} failed: {ex}")
            return []

    worker_safe = _make_safe_worker(safe, _user_id)

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_entries = ex.submit(worker_safe, pfdb.list_entries, None, None,
                               None, None, None, 100)
        f_accs = ex.submit(worker_safe, pfdb.list_accounts, False)
        f_balances = ex.submit(worker_safe, pfr.all_account_balances,
                                None)

    return {
        "entries": f_entries.result(),
        "accounts": f_accs.result(),
        "balances": f_balances.result(),
    }


def fetch_ledger_bundle():
    return _fetch_ledger_bundle_impl(_uid())


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_budget_bundle_impl(_user_id, period):
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, **kw):
        try:
            return fn(*args, **kw)
        except Exception as ex:
            print(f"[budget] {fn.__name__} failed: {ex}")
            return []

    worker_safe = _make_safe_worker(safe, _user_id)

    with ThreadPoolExecutor(max_workers=4) as ex:
        f_rows = ex.submit(worker_safe, pfr.budget_vs_actual, period)
        f_trend = ex.submit(worker_safe, pfr.monthly_spending, 12)
        f_cats = ex.submit(worker_safe, pfdb.list_accounts,
                            True, "expense")
        f_budgets = ex.submit(worker_safe, pfdb.list_budgets, period)

    return {
        "rows": f_rows.result(),
        "trend": f_trend.result(),
        "expense_categories": f_cats.result(),
        "existing_budgets": f_budgets.result(),
    }


def fetch_budget_bundle(period):
    return _fetch_budget_bundle_impl(_uid(), period)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_reimbursement_bundle_impl(_user_id):
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, default=None, **kw):
        try:
            return fn(*args, **kw)
        except Exception:
            return default

    worker_safe = _make_safe_worker(safe, _user_id)

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_summary = ex.submit(worker_safe, invdb.reimbursement_summary,
                               default={})
        f_company = ex.submit(worker_safe, invdb.by_expense_type,
                               "公司報銷", default=[])
        f_assets = ex.submit(worker_safe, pfdb.list_accounts, True,
                              "asset", default=[])

    return {
        "summary": f_summary.result(),
        "company_invoices": f_company.result(),
        "asset_accounts": f_assets.result(),
    }


def fetch_reimbursement_bundle():
    return _fetch_reimbursement_bundle_impl(_uid())


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_credit_cards_bundle_impl(_user_id):
    from concurrent.futures import ThreadPoolExecutor
    from personal_finance import db as pfdb

    def safe(fn, *args, default=None):
        try:
            return fn(*args)
        except Exception:
            return default

    # 第一步喺 main thread 行（已有 session ctx）
    cards = safe(pfdb.list_credit_cards, default=[])
    cards_with_limit = [c for c in cards
                         if (c.get("credit_limit") or 0) > 0]
    if not cards_with_limit:
        return {"cards": [], "balances": {}}

    worker_safe = _make_safe_worker(safe, _user_id)

    with ThreadPoolExecutor(
            max_workers=min(8, len(cards_with_limit))) as ex:
        futures = {
            c["account_code"]:
            ex.submit(worker_safe, pfr.account_balance,
                      c["account_code"], None, True, default=0)
            for c in cards_with_limit
        }
        balances = {code: f.result() for code, f in futures.items()}

    return {"cards": cards_with_limit, "balances": balances}


def fetch_credit_cards_bundle():
    return _fetch_credit_cards_bundle_impl(_uid())
