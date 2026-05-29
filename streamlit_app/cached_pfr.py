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
