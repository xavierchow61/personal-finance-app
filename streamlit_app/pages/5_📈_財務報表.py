"""財務報表 — 收支表、資產負債表、期間對比"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd

from streamlit_app._common import (C, app_header, init_dbs, kpi_card,
                                      render_subpage_nav)

st.set_page_config(
    page_title="財務報表", page_icon="📈", layout="wide",
    initial_sidebar_state="expanded",
)
init_dbs()

app_header("個人記賬", "📈", "收支表 · 資產負債表 · 期間對比")
render_subpage_nav("ledger")

from personal_finance import reports as pfr
import cached_pfr

PERIODS = {
    "本月": "this_month", "上月": "last_month",
    "本年": "this_year", "上年": "last_year",
    "年初至今": "ytd",
}

tab1, tab2, tab3 = st.tabs([
    "💰 收支表（P&L）",
    "🏦 資產負債表",
    "⚖️ 期間對比",
])

# === 收支表 ===
with tab1:
    st.caption("Income Statement — 請選擇期間")
    p_label = st.selectbox("期間", list(PERIODS.keys()),
                            index=0, key="pl_period")
    p_type = PERIODS[p_label]
    start, end = pfr.period_dates(p_type)

    st.markdown(f"**📅 {p_label}**（{start} 至 {end}）")

    with st.spinner("📊 載入收支表..."):
        pl = cached_pfr.income_statement(start, end)
    c1, c2, c3 = st.columns(3)
    kpi_card(c1, "💼 總收入", pl["total_income"], C["success"], "")
    kpi_card(c2, "🛒 總支出", pl["total_expense"], C["warning"], "")
    kpi_card(c3, "📊 淨額", pl["net"],
              C["success"] if pl["net"] >= 0 else C["red"], "")

    st.write("")
    inc, exp = st.columns(2)

    with inc:
        st.subheader("💼 收入")
        if pl["income"]:
            df_i = pd.DataFrame([
                {"類別": f"{i.get('icon') or ''} {i['name']}",
                 "金額 (HKD)": i["amount"]}
                for i in pl["income"]
            ])
            st.dataframe(df_i, hide_index=True, use_container_width=True,
                          column_config={
                              "金額 (HKD)": st.column_config.NumberColumn(
                                  format="$%.2f"),
                          })
        else:
            st.info("此期間並無收入紀錄")

    with exp:
        st.subheader("🛒 支出")
        if pl["expense"]:
            df_e = pd.DataFrame([
                {"類別": f"{e.get('icon') or ''} {e['name']}",
                 "金額 (HKD)": e["amount"]}
                for e in pl["expense"]
            ])
            st.dataframe(df_e, hide_index=True, use_container_width=True,
                          column_config={
                              "金額 (HKD)": st.column_config.NumberColumn(
                                  format="$%.2f"),
                          })
        else:
            st.info("此期間並無支出紀錄")

# === 資產負債表 ===
with tab2:
    st.caption("Balance Sheet — 請選擇截止日期")
    from datetime import date as _d
    as_of = st.date_input("截止日期", _d.today(), key="bs_date")
    with st.spinner("🏦 載入資產負債表..."):
        bs = cached_pfr.balance_sheet(as_of.isoformat())

    c1, c2, c3 = st.columns(3)
    kpi_card(c1, "💰 資產總額", bs["total_assets"], C["success"], "")
    kpi_card(c2, "💳 負債總額", bs["total_liabilities"], C["red"], "")
    kpi_card(c3, "📊 淨資產", bs["net_worth"], C["accent"], "")

    st.write("")
    ba, bl = st.columns(2)
    with ba:
        st.subheader("💵 資產")
        if bs["assets"]:
            df_a = pd.DataFrame([
                {"帳戶": f"{a.get('icon') or ''} {a['name']}",
                 "餘額 (HKD)": a["balance"]}
                for a in bs["assets"]
            ])
            st.dataframe(df_a, hide_index=True, use_container_width=True,
                          column_config={
                              "餘額 (HKD)": st.column_config.NumberColumn(
                                  format="$%.2f"),
                          })
    with bl:
        st.subheader("💳 負債")
        if bs["liabilities"]:
            df_l = pd.DataFrame([
                {"帳戶": f"{l.get('icon') or ''} {l['name']}",
                 "餘額 (HKD)": l["balance"]}
                for l in bs["liabilities"]
            ])
            st.dataframe(df_l, hide_index=True, use_container_width=True,
                          column_config={
                              "餘額 (HKD)": st.column_config.NumberColumn(
                                  format="$%.2f"),
                          })
        else:
            st.info("🎉 並無負債")

# === 期間對比 ===
with tab3:
    st.caption("Period Compare — 並排比較兩個期間")
    cc1, cc2 = st.columns(2)
    pa_label = cc1.selectbox("期間 A", list(PERIODS.keys()),
                              index=0, key="cmp_a")
    pb_label = cc2.selectbox("期間 B", list(PERIODS.keys()),
                              index=1, key="cmp_b")

    with st.spinner("⚖️ 載入期間對比..."):
        cmp = cached_pfr.period_compare(PERIODS[pa_label], PERIODS[pb_label])

    summary_df = pd.DataFrame([
        {"指標": "💼 收入",
         pa_label: cmp["income_a"], pb_label: cmp["income_b"],
         "差異": cmp["income_diff"]},
        {"指標": "🛒 支出",
         pa_label: cmp["expense_a"], pb_label: cmp["expense_b"],
         "差異": cmp["expense_diff"]},
        {"指標": "📊 淨額",
         pa_label: cmp["net_a"], pb_label: cmp["net_b"],
         "差異": cmp["net_diff"]},
    ])
    st.dataframe(summary_df, hide_index=True, use_container_width=True,
                  column_config={
                      pa_label: st.column_config.NumberColumn(format="$%.2f"),
                      pb_label: st.column_config.NumberColumn(format="$%.2f"),
                      "差異": st.column_config.NumberColumn(format="$%.2f"),
                  })

    if cmp["categories"]:
        st.subheader("各類別細項對比")
        cat_df = pd.DataFrame([
            {"類別": f"{c.get('icon') or ''} {c['name']}",
             pa_label: c["amount_a"],
             pb_label: c["amount_b"],
             "差異": c["diff"],
             "變化百分比": c.get("pct_change")}
            for c in cmp["categories"]
        ])
        st.dataframe(cat_df, hide_index=True, use_container_width=True,
                      column_config={
                          pa_label: st.column_config.NumberColumn(format="$%.2f"),
                          pb_label: st.column_config.NumberColumn(format="$%.2f"),
                          "差異": st.column_config.NumberColumn(format="$%.2f"),
                          "變化百分比": st.column_config.NumberColumn(
                              format="%.1f%%"),
                      })
