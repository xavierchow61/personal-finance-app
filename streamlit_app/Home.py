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

# 儀表板不顯示頁面標題（節省版面，直接顯示 KPI）
app_header("")

check_api_key()

from personal_finance import reports as pfr
import cached_pfr  # cached wrappers for speed

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
start, end = cached_pfr.period_dates(period_type)

# === KPI 卡片（用 cached pfr 加速 + 防呆）===
as_of = end if period_type != "all" else None
try:
    with st.spinner("📊 載入資料中..."):
        nw = cached_pfr.net_worth(as_of)
        pl = cached_pfr.income_statement(start, end)
except Exception as ex:
    st.error(
        f"⚠️ 無法載入資料：{type(ex).__name__}\n\n"
        f"{ex}\n\n"
        "若係首次用，可能需要等 1-2 分鐘建立帳戶。"
    )
    nw = {"assets": 0, "liabilities": 0, "net_worth": 0}
    pl = {"total_expense": 0, "total_income": 0, "net": 0,
          "income": [], "expense": []}

c1, c2, c3, c4 = st.columns(4)
kpi_card(c1, "資產總額", nw["assets"], C["success"], "💰", "HKD")
kpi_card(c2, "負債總額", nw["liabilities"], C["red"], "💳", "HKD")
kpi_card(c3, "淨資產", nw["net_worth"], C["accent"], "📊", "HKD")
kpi_card(c4, f"{period_label} 支出",
         pl["total_expense"], C["warning"], "🛒", "本期累計")

st.write("")

# === 💳 信用卡儀表板 ===
try:
    from personal_finance import db as pfdb
    from datetime import date as _d, timedelta as _td

    def _next_due_date(due_day, today=None):
        """計算今日之後最近嘅還款日"""
        if not due_day:
            return None
        today = today or _d.today()
        import calendar
        try:
            target = today.replace(day=due_day)
        except ValueError:
            last = calendar.monthrange(today.year, today.month)[1]
            target = today.replace(day=min(due_day, last))
        if target <= today:
            m, y = today.month + 1, today.year
            if m > 12:
                m, y = 1, y + 1
            try:
                target = today.replace(year=y, month=m, day=due_day)
            except ValueError:
                last = calendar.monthrange(y, m)[1]
                target = today.replace(
                    year=y, month=m, day=min(due_day, last))
        return target

    cards = pfdb.list_credit_cards()
    cards_with_limit = [c for c in cards
                         if (c.get("credit_limit") or 0) > 0]

    if cards_with_limit:
        st.markdown(
            f"<h3 style='color:{C['text']};margin-top:1rem;'>"
            f"💳 信用卡概覽</h3>",
            unsafe_allow_html=True,
        )

        total_limit = 0.0
        total_used = 0.0
        card_details = []
        today_d = _d.today()
        for cc in cards_with_limit:
            code = cc["account_code"]
            balance = abs(cached_pfr.account_balance(code,
                                                       in_hkd=True))
            limit = float(cc["credit_limit"])
            total_limit += limit
            total_used += balance
            util = (balance / limit * 100) if limit > 0 else 0
            next_due = _next_due_date(cc.get("due_day"), today_d)
            days_left = ((next_due - today_d).days
                         if next_due else None)
            card_details.append({
                "name": cc.get("account_name") or code,
                "icon": cc.get("account_icon") or "💳",
                "last4": cc.get("card_last4") or "—",
                "balance": balance,
                "limit": limit,
                "util": util,
                "days_left": days_left,
            })

        total_available = total_limit - total_used
        avg_util = (total_used / total_limit * 100
                    if total_limit > 0 else 0)
        # 配色：使用率越高越紅
        util_color = (C["red"] if avg_util > 80
                       else C["warning"] if avg_util > 50
                       else C["success"])

        cc1, cc2, cc3, cc4 = st.columns(4)
        kpi_card(cc1, "總信用額度", total_limit, C["info"],
                  "💳", f"{len(cards_with_limit)} 張卡")
        kpi_card(cc2, "已用金額", total_used, C["warning"],
                  "📊", "HKD")
        kpi_card(cc3, "可用額度", total_available,
                  C["success"], "✨", "HKD")
        kpi_card(cc4, "平均使用率", f"{avg_util:.0f}%",
                  util_color, "📈",
                  ("🔴 高" if avg_util > 80
                   else "🟡 中" if avg_util > 50
                   else "🟢 健康"))

        # === 警示橫幅 ===
        # 1. 即將還款（≤ 7 日）
        due_soon = [c for c in card_details
                    if c["days_left"] is not None
                    and c["days_left"] <= 7]
        if due_soon:
            lines = [
                f"• {c['icon']} {c['name']}（****{c['last4']}）"
                f" — 還剩 **{c['days_left']} 日**，"
                f"應還 **${c['balance']:,.0f}**"
                for c in due_soon
            ]
            st.warning(
                "⏰ **即將還款提示**\n\n" + "\n\n".join(lines)
            )

        # 2. 高使用率（> 80%）
        high_util = [c for c in card_details if c["util"] > 80]
        if high_util:
            lines = [
                f"• {c['icon']} {c['name']}（****{c['last4']}）"
                f" — 用咗 **{c['util']:.0f}%**"
                f"（${c['balance']:,.0f} / ${c['limit']:,.0f}）"
                for c in high_util
            ]
            st.error(
                "🔴 **高使用率警示**\n\n" + "\n\n".join(lines)
            )

        # === 📅 還款行事曆（未來 30 日 timeline）===
        upcoming_30d = sorted(
            [c for c in card_details
             if c["days_left"] is not None
             and 0 <= c["days_left"] <= 30],
            key=lambda x: x["days_left"],
        )
        if upcoming_30d:
            st.markdown(
                f"<h4 style='color:{C['text']};margin-top:0.5rem;'>"
                f"📅 未來 30 日還款行事曆</h4>",
                unsafe_allow_html=True,
            )
            cal_html = (
                '<div style="background:white;'
                'border:2px solid rgba(0,166,224,0.3);'
                'border-radius:14px;padding:0.8rem 1rem;'
                'box-shadow:0 4px 14px rgba(0,120,186,0.12);">'
            )
            for c in upcoming_30d:
                # 顏色由倒數決定
                if c["days_left"] <= 3:
                    bg = "rgba(230,0,18,0.15)"
                    edge = "#E60012"
                elif c["days_left"] <= 7:
                    bg = "rgba(255,199,0,0.18)"
                    edge = "#FFC700"
                else:
                    bg = "rgba(0,166,224,0.10)"
                    edge = "#00A6E0"
                cal_html += (
                    f'<div style="display:flex;align-items:center;'
                    f'background:{bg};border-left:4px solid {edge};'
                    f'border-radius:8px;padding:0.5rem 0.8rem;'
                    f'margin:0.35rem 0;">'
                    f'<div style="flex:0 0 70px;font-weight:700;'
                    f'color:{edge};font-size:1.1rem;">'
                    f'{c["days_left"]} 日</div>'
                    f'<div style="flex:1;color:#1A1A2E;">'
                    f'{c["icon"]} <b>{c["name"]}</b> '
                    f'<span style="color:#6B7BA0;font-size:0.85rem;">'
                    f'****{c["last4"]}</span></div>'
                    f'<div style="flex:0 0 auto;font-weight:700;'
                    f'color:#1A1A2E;font-size:1.05rem;">'
                    f'${c["balance"]:,.0f}</div></div>'
                )
            cal_html += '</div>'
            st.markdown(cal_html, unsafe_allow_html=True)

        st.write("")
except Exception:
    # 信用卡資料庫未 migrate 或無資料 → 靜默跳過
    pass

st.write("")

# === 兩欄佈局：圓餅圖 / 五大單據 ===
left, right = st.columns([1, 1])

with left:
    st.markdown(
        f"<h3 style='color:{C['text']}'>🥧 各類別支出佔比</h3>",
        unsafe_allow_html=True,
    )
    cats = cached_pfr.spending_by_category(start, end)
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
    top = cached_pfr.invoices_top_n_by_amount(5)
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
balances = cached_pfr.all_account_balances(as_of)
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
