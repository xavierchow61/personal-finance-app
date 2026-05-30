"""個人貸款管理 — 按揭、汽車、個人、信用卡分期"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd
from datetime import date as _d, timedelta as _td
import calendar

from streamlit_app._common import (
    C, app_header, init_dbs, kpi_card, render_subpage_nav,
)

st.set_page_config(
    page_title="貸款管理", page_icon="💸", layout="wide",
    initial_sidebar_state="expanded",
)
init_dbs()

app_header("個人記賬", "💸",
           "按揭 · 汽車 · 個人 · 分期 — 總覽與還款追蹤")
render_subpage_nav("ledger")

from personal_finance import db as pfdb

LOAN_TYPES = {
    "mortgage": "🏠 按揭",
    "auto": "🚗 汽車貸款",
    "personal": "💼 個人貸款",
    "instalment": "💳 信用卡分期",
    "student": "🎓 學生貸款",
    "other": "📋 其他",
}

# ============ 載入所有貸款（防呆） ============
try:
    pfdb.init_db()
    loans = pfdb.list_loans()
except Exception as ex:
    st.error(f"⚠️ 無法載入貸款資料：{type(ex).__name__}: {ex}")
    loans = []

active_loans = [l for l in loans if l.get("status") == "active"]

# ============ KPI 總覽 ============
if active_loans:
    total_principal = sum(l["principal"] for l in active_loans)
    total_monthly = sum(l.get("monthly_payment") or 0
                          for l in active_loans)
    n_active = len(active_loans)

    # 計算未來 30 日內到期還款
    today = _d.today()
    upcoming = 0
    upcoming_amount = 0.0
    for l in active_loans:
        if l.get("due_day"):
            try:
                target = today.replace(day=l["due_day"])
            except ValueError:
                last = calendar.monthrange(
                    today.year, today.month)[1]
                target = today.replace(
                    day=min(l["due_day"], last))
            if target < today:
                m, y = today.month + 1, today.year
                if m > 12:
                    m, y = 1, y + 1
                try:
                    target = today.replace(
                        year=y, month=m, day=l["due_day"])
                except ValueError:
                    last = calendar.monthrange(y, m)[1]
                    target = today.replace(
                        year=y, month=m,
                        day=min(l["due_day"], last))
            if (target - today).days <= 30:
                upcoming += 1
                upcoming_amount += l.get("monthly_payment") or 0

    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, "進行中貸款", n_active, C["info"],
              "💼", f"{n_active} 筆")
    kpi_card(c2, "本金總額", total_principal, C["red"],
              "💰", "HKD")
    kpi_card(c3, "每月應供", total_monthly, C["warning"],
              "📅", "HKD/月")
    kpi_card(c4, "未來 30 日到期",
              upcoming_amount, C["accent"],
              "⏰", f"{upcoming} 筆")
    st.write("")

# ============ 貸款列表 ============
st.markdown(
    f"<h3 style='color:{C['text']}'>📋 貸款清單</h3>",
    unsafe_allow_html=True,
)

# 篩選
flt_col1, flt_col2 = st.columns(2)
status_filter = flt_col1.selectbox(
    "狀態",
    ["（全部）", "active 進行中", "paid 已還清", "cancelled 取消"],
    key="loan_status_flt",
)
type_filter = flt_col2.selectbox(
    "類型",
    ["（全部）"] + list(LOAN_TYPES.values()),
    key="loan_type_flt",
)

filtered = loans
if status_filter != "（全部）":
    code = status_filter.split()[0]
    filtered = [l for l in filtered if l.get("status") == code]
if type_filter != "（全部）":
    type_code = next(
        (k for k, v in LOAN_TYPES.items() if v == type_filter),
        None)
    if type_code:
        filtered = [l for l in filtered
                     if l.get("loan_type") == type_code]

if filtered:
    df_loans = pd.DataFrame([
        {
            "ID": l["loan_id"],
            "名稱": l["name"],
            "類型": LOAN_TYPES.get(l.get("loan_type"),
                                    l.get("loan_type")),
            "銀行": l.get("bank") or "—",
            "本金": l["principal"],
            "年利率": f"{(l['interest_rate'] or 0)*100:.2f}%",
            "期數": f"{l['term_months']} 月",
            "每月應供": l.get("monthly_payment") or 0,
            "開始日": l.get("start_date") or "—",
            "還款日": l.get("due_day") or "—",
            "狀態": l.get("status") or "active",
        }
        for l in filtered
    ])
    sel_loan = st.dataframe(
        df_loans, hide_index=True, use_container_width=True,
        on_select="rerun", selection_mode="single-row",
        column_config={
            "本金": st.column_config.NumberColumn(format="$%.2f"),
            "每月應供": st.column_config.NumberColumn(format="$%.2f"),
        },
    )

    # === 編輯選定貸款 ===
    if sel_loan.selection.rows:
        sel_id = int(df_loans.iloc[
            sel_loan.selection.rows[0]]["ID"])
        ln = pfdb.get_loan(sel_id)
        if ln:
            st.divider()
            with st.expander(
                f"✏️ 編輯：{ln['name']} (ID {sel_id})",
                expanded=True,
            ):
                # 計算累計利息（簡化版）
                total_pay = (ln.get("monthly_payment") or 0
                             ) * ln["term_months"]
                total_interest = total_pay - ln["principal"]

                ic1, ic2, ic3 = st.columns(3)
                ic1.metric("總還款額", f"${total_pay:,.2f}")
                ic2.metric("總利息", f"${total_interest:,.2f}",
                            f"{(total_interest/ln['principal']*100):.1f}%"
                            if ln["principal"] else "—")
                ic3.metric("每月應供",
                            f"${ln.get('monthly_payment') or 0:,.2f}")

                with st.form(f"edit_loan_{sel_id}"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        ed_name = st.text_input(
                            "名稱", ln["name"])
                        type_label = LOAN_TYPES.get(
                            ln.get("loan_type"), "📋 其他")
                        ed_type_label = st.selectbox(
                            "類型",
                            list(LOAN_TYPES.values()),
                            index=list(LOAN_TYPES.values()
                                       ).index(type_label)
                            if type_label in LOAN_TYPES.values()
                            else 0,
                        )
                        ed_type = next(
                            (k for k, v in LOAN_TYPES.items()
                             if v == ed_type_label), "other")
                        ed_bank = st.text_input(
                            "銀行 / 機構",
                            ln.get("bank") or "",
                        )
                        ed_status = st.selectbox(
                            "狀態",
                            ["active", "paid", "cancelled"],
                            index=["active", "paid", "cancelled"
                                    ].index(ln.get("status")
                                            or "active"),
                        )
                    with ec2:
                        ed_principal = st.number_input(
                            "本金 (HKD)",
                            value=float(ln["principal"]),
                            min_value=0.0, format="%.2f",
                        )
                        ed_rate = st.number_input(
                            "年利率 % (例 4.5)",
                            value=float(
                                (ln["interest_rate"] or 0)*100),
                            min_value=0.0, format="%.3f",
                        )
                        ed_term = st.number_input(
                            "期數（月）",
                            value=int(ln["term_months"]),
                            min_value=1, step=1,
                        )
                        ed_due = st.number_input(
                            "每月還款日 (1-31)",
                            value=int(ln.get("due_day") or 1),
                            min_value=1, max_value=31, step=1,
                        )
                    ed_start = st.text_input(
                        "開始日 (YYYY-MM-DD)",
                        ln.get("start_date") or "",
                    )
                    ed_notes = st.text_area(
                        "備註", ln.get("notes") or "",
                    )

                    eb1, eb2 = st.columns(2)
                    if eb1.form_submit_button(
                            "💾 儲存", type="primary",
                            use_container_width=True):
                        try:
                            mp = pfdb.calc_monthly_payment(
                                ed_principal, ed_rate / 100,
                                ed_term)
                            pfdb.update_loan(
                                sel_id,
                                name=ed_name,
                                loan_type=ed_type,
                                bank=ed_bank or None,
                                principal=ed_principal,
                                interest_rate=ed_rate / 100,
                                term_months=ed_term,
                                monthly_payment=mp,
                                start_date=ed_start,
                                due_day=ed_due,
                                status=ed_status,
                                notes=ed_notes or None,
                            )
                            st.success(f"✅ 已更新 #{sel_id}")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"更新失敗：{ex}")
                    if eb2.form_submit_button(
                            "🗑️ 刪除", type="secondary",
                            use_container_width=True):
                        pfdb.delete_loan(sel_id)
                        st.success("已刪除")
                        st.rerun()
else:
    st.info("尚無符合條件的貸款紀錄。請於下方新增。")

# ============ 新增貸款 ============
st.divider()
with st.expander("➕ 新增貸款", expanded=not bool(loans)):
    # 注意：不用 st.form，讓試算可即時更新
    n1, n2 = st.columns(2)
    with n1:
        nl_name = st.text_input(
            "名稱",
            placeholder="例：東亞 30 年按揭 / 中銀汽車貸款",
            key="nl_name",
        )
        nl_type_label = st.selectbox(
            "類型", list(LOAN_TYPES.values()),
            key="nl_type_label",
        )
        nl_type = next(
            (k for k, v in LOAN_TYPES.items()
             if v == nl_type_label), "other")
        nl_bank = st.text_input(
            "銀行 / 機構",
            placeholder="例：HSBC / BEA / 中銀",
            key="nl_bank",
        )
        nl_start = st.date_input(
            "開始日", _d.today(), key="nl_start")
    with n2:
        nl_principal = st.number_input(
            "本金 (HKD)",
            value=100000.0, min_value=0.0, format="%.2f",
            key="nl_principal",
        )
        nl_rate = st.number_input(
            "年利率 % (例 4.5)",
            value=4.5, min_value=0.0, format="%.3f",
            key="nl_rate",
        )
        nl_term = st.number_input(
            "期數（月）",
            value=360, min_value=1, step=1,
            help="按揭 30 年 = 360, 5 年 = 60",
            key="nl_term",
        )
        nl_due = st.number_input(
            "每月還款日 (1-31)",
            value=1, min_value=1, max_value=31, step=1,
            key="nl_due",
        )

    # 即時試算（即時更新！）
    try:
        if nl_principal > 0:
            preview_emi = pfdb.calc_monthly_payment(
                nl_principal, nl_rate / 100, nl_term)
            preview_total = preview_emi * nl_term
            preview_interest = preview_total - nl_principal
            pct = preview_interest / nl_principal * 100
            st.markdown(
                f"""
                <div style="background:rgba(0,166,224,0.12);
                            border-left:4px solid #00A6E0;
                            border-radius:10px;
                            padding:0.8rem 1.1rem;
                            color:#1A1A2E;
                            font-size:0.95rem;
                            line-height:1.6;
                            margin:0.6rem 0;">
                    📊 <b>即時試算</b>（隨輸入自動更新）<br>
                    每月供款：
                    <b style="color:#0078BA;font-size:1.15rem;">
                        HK${preview_emi:,.2f}
                    </b><br>
                    總還款：<b>HK${preview_total:,.0f}</b>
                    &nbsp;·&nbsp;
                    總利息：<b style="color:#E60012;">
                        HK${preview_interest:,.0f}
                    </b>
                    <span style="color:#6B7BA0;">
                        ({pct:.1f}%)
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    nl_notes = st.text_area(
        "備註（選填）",
        placeholder="例：罰息期 / 提前還款條款",
        key="nl_notes",
    )

    if st.button(
            "✨ 建立貸款", type="primary",
            use_container_width=True,
            key="nl_create_btn"):
            if not nl_name.strip():
                st.error("名稱不能為空")
            elif nl_principal <= 0:
                st.error("本金必須大於零")
            else:
                try:
                    loan_id = pfdb.create_loan(
                        name=nl_name.strip(),
                        loan_type=nl_type,
                        bank=nl_bank or None,
                        principal=nl_principal,
                        interest_rate=nl_rate / 100,
                        term_months=int(nl_term),
                        start_date=nl_start.isoformat(),
                        due_day=int(nl_due),
                        notes=nl_notes or None,
                    )
                    st.success(
                        f"✅ 建立成功！貸款 #{loan_id}：{nl_name}"
                    )
                    st.rerun()
                except Exception as ex:
                    st.error(f"建立失敗：{ex}")
