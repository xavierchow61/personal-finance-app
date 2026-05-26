"""預算與實績對比"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd

from streamlit_app._common import C, app_header, init_dbs, plotly_glass_layout

st.set_page_config(
    page_title="預算", page_icon="🎯", layout="wide",
    initial_sidebar_state="expanded",
)
init_dbs()

app_header("預算與實績", "🎯", "月度預算追蹤、超支警告及歷史走勢")

from personal_finance import db as pfdb, reports as pfr
from datetime import date

# === 選擇期間 ===
period = st.text_input("期間（YYYY-MM）", value=date.today().strftime("%Y-%m"))

# === 預算與實績對比 ===
rows = pfr.budget_vs_actual(period)
if not rows:
    st.info("此月份尚未設定預算或無支出紀錄。請於下方「設定預算」處設定。")
else:
    df = pd.DataFrame([
        {
            "類別": f"{r.get('icon') or ''} {r['name']}",
            "預算": r.get("budget") or 0,
            "實績": r["amount"],
            "餘額": ((r.get("budget") or 0) - r["amount"]
                      if r.get("budget") else None),
            "使用率": r.get("pct_used"),
        }
        for r in rows
    ])
    st.dataframe(df, hide_index=True, use_container_width=True,
                  column_config={
                      "預算": st.column_config.NumberColumn(format="$%.2f"),
                      "實績": st.column_config.NumberColumn(format="$%.2f"),
                      "餘額": st.column_config.NumberColumn(format="$%.2f"),
                      "使用率": st.column_config.ProgressColumn(
                          format="%.0f%%", min_value=0, max_value=150),
                  })

    # 超支警告
    over = [r for r in rows if r.get("pct_used") and r["pct_used"] > 100]
    if over:
        st.error(f"⚠️ 有 {len(over)} 個類別超出預算：" +
                  "、".join(f"{o['name']}（{o['pct_used']:.0f}%）"
                           for o in over))

st.divider()

# === 設定預算 ===
with st.expander("➕ 設定或修改預算"):
    cats = pfdb.list_accounts(account_type="expense")
    existing = {b["account_code"]: b["amount"]
                 for b in pfdb.list_budgets(period=period)}

    with st.form("budget_form"):
        st.caption(f"設定 {period} 的預算（留空表示不設定）")
        cols = st.columns(3)
        new_vals = {}
        for i, c in enumerate(cats):
            with cols[i % 3]:
                val = st.text_input(
                    f"{c.get('icon') or ''} {c['name']}",
                    value=str(existing.get(c["code"], "")),
                    key=f"bud_{c['code']}",
                )
                new_vals[c["code"]] = val
        if st.form_submit_button("💾 儲存全部預算", type="primary"):
            n_set = 0
            for code, v in new_vals.items():
                v = v.strip()
                if v:
                    try:
                        pfdb.set_budget(code, period, float(v))
                        n_set += 1
                    except ValueError:
                        pass
            st.success(f"✅ 已設定 {n_set} 個類別的預算")
            st.rerun()

# === 過去 12 個月走勢 ===
st.divider()
st.subheader("📈 過去 12 個月支出走勢")
trend = pfr.monthly_spending(12)
if not trend:
    st.info("尚未有任何支出資料，無法繪製走勢圖。")
elif len(trend) == 1:
    only = trend[0]
    st.info(
        f"目前只有 **{only['month']}** 月有支出資料（共 "
        f"${only['amount']:,.2f}），需要累積更多月份方可顯示走勢。"
    )
    st.metric(f"📅 {only['month']}", f"${only['amount']:,.2f}")
else:
    import plotly.graph_objects as go
    df_t = pd.DataFrame(trend).sort_values("month")
    # 強制把 month 轉為字串型類別，避免 Plotly 自動補滿整年
    df_t["month"] = df_t["month"].astype(str)
    n_bars = len(df_t)
    # 動態柱寬：少於 4 根時更窄；多於 6 根時較寬
    bar_width = 0.35 if n_bars <= 3 else (0.55 if n_bars <= 6 else 0.7)

    fig = go.Figure(
        data=[
            go.Bar(
                x=df_t["month"],
                y=df_t["amount"],
                text=[f"${v:,.0f}" for v in df_t["amount"]],
                textposition="outside",
                textfont=dict(color="#f1f5f9", size=12, family="Inter"),
                width=bar_width,
                marker=dict(
                    color="#00A6E0",
                    line=dict(color="#0078BA", width=1.5),
                ),
                hovertemplate="<b>%{x}</b><br>"
                              "支出：$%{y:,.2f}<extra></extra>",
            )
        ]
    )
    plotly_glass_layout(fig, height=400)
    fig.update_layout(
        xaxis=dict(
            type="category",          # ← 關鍵：避免自動展開日期軸
            title="月份",
            tickfont=dict(color="#cbd5e1"),
            showgrid=False,
        ),
        yaxis=dict(
            title="支出金額（HKD）",
            gridcolor="rgba(255,255,255,0.08)",
            tickfont=dict(color="#cbd5e1"),
            zeroline=False,
        ),
        bargap=0.4,
        showlegend=False,
        margin=dict(t=40, b=50, l=60, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # 簡單統計
    s1, s2, s3 = st.columns(3)
    avg = sum(t["amount"] for t in trend) / len(trend)
    mx = max(trend, key=lambda t: t["amount"])
    mn = min(trend, key=lambda t: t["amount"])
    s1.metric("月度平均", f"${avg:,.2f}")
    s2.metric("最高月份", f"${mx['amount']:,.2f}", mx["month"])
    s3.metric("最低月份", f"${mn['amount']:,.2f}", mn["month"])
