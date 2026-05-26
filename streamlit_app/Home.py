"""個人理財 Streamlit 首頁 / Glassmorphism 儀表板"""
import streamlit as st

from _common import (
    C, PALETTE, app_header, check_api_key, init_dbs, kpi_card,
    plotly_glass_layout,
)

st.set_page_config(
    page_title="個人理財",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_dbs()

app_header("個人理財 儀表板", "💎",
            "AI 提取單據 · 自動入賬 · 預算追蹤 · 隨時隨地查閱")

check_api_key()

from personal_finance import reports as pfr

PERIODS = {
    "本月": "this_month",
    "上月": "last_month",
    "本年": "this_year",
    "上年": "last_year",
    "全部": "all",
}
col_sel, _ = st.columns([2, 5])
period_label = col_sel.selectbox("📅 期間", list(PERIODS.keys()), index=0)
period_type = PERIODS[period_label]
start, end = pfr.period_dates(period_type)

# === KPI 卡片 ===
as_of = end if period_type != "all" else None
nw = pfr.net_worth(as_of)
pl = pfr.income_statement(start, end)

c1, c2, c3, c4 = st.columns(4)
kpi_card(c1, "資產總額", nw["assets"], C["success"], "💰", "HKD")
kpi_card(c2, "負債總額", nw["liabilities"], C["red"], "💳", "HKD")
kpi_card(c3, "淨資產", nw["net_worth"], C["accent"], "📊", "HKD")
kpi_card(c4, f"{period_label} 支出",
         pl["total_expense"], C["warning"], "🛒", "本期累計")

st.write("")
st.write("")

# === 兩欄佈局：圓餅圖 / 五大單據 ===
left, right = st.columns([1, 1])

with left:
    st.markdown(
        f"<h3 style='color:{C['text']}'>🥧 各類別支出佔比</h3>",
        unsafe_allow_html=True,
    )
    cats = pfr.spending_by_category(start, end)
    if cats:
        import plotly.express as px
        import pandas as pd
        df = pd.DataFrame([
            {"類別": f"{c.get('icon', '')} {c['name']}",
             "金額": c["amount"]}
            for c in cats if c["amount"] > 0
        ])
        if not df.empty:
            # 哆啦 A 夢配色 — 藍 + 紅 + 黃 + 粉 + 綠
            glass_palette = [
                "#00A6E0",   # 哆啦藍
                "#E60012",   # 鼻子紅
                "#FFC700",   # 鈴鐺黃
                "#FFB7C8",   # 舌頭粉
                "#00B894",   # 開心綠
                "#5DADE2",   # 中藍
                "#7DD3FC",   # 天空藍
                "#FF7043",   # 暖橙
                "#9C27B0",   # 紫
            ]
            fig = px.pie(
                df, values="金額", names="類別", hole=0.55,
                color_discrete_sequence=glass_palette,
            )
            fig.update_traces(
                textposition="outside",
                textinfo="label+percent",
                marker=dict(line=dict(color="rgba(255,255,255,0.2)", width=2)),
                hovertemplate="<b>%{label}</b><br>"
                              "$%{value:,.2f}<br>%{percent}<extra></extra>",
            )
            plotly_glass_layout(fig, height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("此期間並無支出資料")
    else:
        st.info("尚無支出資料。請先至「📤 提取單據」匯入單據。")

with right:
    st.markdown(
        f"<h3 style='color:{C['text']}'>🏆 金額最高的五張單據</h3>",
        unsafe_allow_html=True,
    )
    import database as invdb
    top = invdb.top_n_by_amount(5)
    if top:
        import pandas as pd
        df = pd.DataFrame([
            {
                "排名": i + 1,
                "日期": inv.get("purchase_date") or "—",
                "商戶": inv.get("store_name") or "—",
                "類別": inv.get("category") or "—",
                "金額": inv.get("total_amount") or 0,
            }
            for i, inv in enumerate(top)
        ])
        st.dataframe(df, hide_index=True, use_container_width=True,
                      column_config={
                          "金額": st.column_config.NumberColumn(format="$%.2f"),
                      })
    else:
        st.info("尚未有單據紀錄")

st.write("")

# === 帳戶餘額 ===
st.markdown(
    f"<h3 style='color:{C['text']}'>🏦 各帳戶餘額</h3>",
    unsafe_allow_html=True,
)
balances = pfr.all_account_balances(as_of)
assets = [b for b in balances if b["account_type"] == "asset"]
liabs = [b for b in balances if b["account_type"] == "liability"]

col_a, col_l = st.columns(2)
with col_a:
    st.markdown(
        f"<p style='color:{C['success']}; font-weight:600; "
        f"font-size:1.05rem'>💵 資產</p>",
        unsafe_allow_html=True,
    )
    import pandas as pd
    df_a = pd.DataFrame([
        {
            "帳戶": f"{a.get('icon') or ''} {a['name']}",
            "餘額 (HKD)": a["balance"],
        }
        for a in assets if abs(a["balance"]) > 0.005 or a["code"] == "CASH"
    ])
    if not df_a.empty:
        st.dataframe(df_a, hide_index=True, use_container_width=True,
                      column_config={
                          "餘額 (HKD)": st.column_config.NumberColumn(
                              format="$%.2f"),
                      })

with col_l:
    st.markdown(
        f"<p style='color:{C['red']}; font-weight:600; "
        f"font-size:1.05rem'>💳 負債</p>",
        unsafe_allow_html=True,
    )
    df_l = pd.DataFrame([
        {
            "帳戶": f"{l.get('icon') or ''} {l['name']}",
            "餘額 (HKD)": l["balance"],
        }
        for l in liabs if abs(l["balance"]) > 0.005
    ])
    if not df_l.empty:
        st.dataframe(df_l, hide_index=True, use_container_width=True,
                      column_config={
                          "餘額 (HKD)": st.column_config.NumberColumn(
                              format="$%.2f"),
                      })
    else:
        st.info("🎉 並無負債")

# === 側欄：補上當前期間資訊（玻璃導航已由 app_header 渲染）===
with st.sidebar:
    st.caption(f"📅 {period_label}\n\n{start} 至 {end}")
