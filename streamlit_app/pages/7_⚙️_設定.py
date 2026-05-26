"""進階設定 — 匯率 / 付款方式對應 / 期間鎖定 / 專案管理"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd

from streamlit_app._common import C, app_header, init_dbs

st.set_page_config(
    page_title="設定", page_icon="⚙️", layout="wide",
    initial_sidebar_state="expanded",
)
init_dbs()

app_header("進階設定", "⚙️",
           "匯率 · 付款方式對應 · 期間鎖定 · 專案管理")

from personal_finance import db as pfdb, seed as pfseed

tab1, tab2, tab3, tab4 = st.tabs([
    "💱 外幣匯率",
    "🔗 付款方式對應",
    "🔒 期間鎖定",
    "🎯 專案管理",
])

# ============ Tab 1: 外幣匯率 ============
with tab1:
    st.caption("設定各幣別對 HKD 的匯率（影響多幣別記賬報表）")

    rates = pfdb.list_fx_rates()
    if rates:
        df_fx = pd.DataFrame([
            {
                "ID": r["fx_id"],
                "幣別": r["currency"],
                "對 HKD 匯率": r["rate_to_hkd"],
                "生效日期": r.get("as_of_date") or "—",
                "備註": r.get("notes") or "",
            }
            for r in rates
        ])
        st.dataframe(df_fx, hide_index=True, use_container_width=True,
                      column_config={
                          "對 HKD 匯率": st.column_config.NumberColumn(
                              format="%.4f"),
                      })
    else:
        st.info("尚未設定任何匯率。HKD 預設 1.0")

    st.divider()
    with st.expander("➕ 新增 / 更新匯率"):
        with st.form("fx_form"):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                curr = st.selectbox(
                    "幣別", ["USD", "JPY", "CNY", "EUR", "GBP",
                              "AUD", "CAD", "SGD", "TWD", "KRW"])
            with fc2:
                rate = st.number_input("對 HKD 匯率", value=1.0,
                                        format="%.4f", min_value=0.0001)
            with fc3:
                from datetime import date as _d
                as_of = st.date_input("生效日期", _d.today())
            notes = st.text_input("備註（選填）", "")

            if st.form_submit_button("💾 儲存匯率", type="primary"):
                try:
                    pfdb.set_fx_rate(curr, rate,
                                       as_of_date=as_of.isoformat(),
                                       notes=notes or None)
                    st.success(f"✅ 已設定 {curr} = {rate:.4f} HKD")
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

# ============ Tab 2: 付款方式對應 ============
with tab2:
    st.caption(
        "設定 OCR 提取出來的「付款方式」字眼 → 對應到哪個帳戶。"
        "例如「PayMe」→ PAYME；「HSBC Visa」→ HSBC_VISA"
    )

    aliases = pfdb.list_payment_aliases()
    if aliases:
        df_al = pd.DataFrame([
            {
                "ID": a["alias_id"],
                "關鍵字（部份匹配）": a["keyword"],
                "對應帳戶": a["account_code"],
                "備註": a.get("notes") or "",
            }
            for a in aliases
        ])
        sel = st.dataframe(df_al, hide_index=True,
                            use_container_width=True,
                            on_select="rerun",
                            selection_mode="single-row")
        if sel.selection.rows:
            del_id = int(df_al.iloc[sel.selection.rows[0]]["ID"])
            if st.button(f"🗑️ 刪除選定的對應 #{del_id}",
                          type="secondary"):
                pfdb.delete_payment_alias(del_id)
                st.success(f"已刪除 #{del_id}")
                st.rerun()
    else:
        st.info("尚未設定任何對應。系統會用 fallback 自動分類。")

    st.divider()
    al_c1, al_c2 = st.columns(2)
    with al_c1:
        if st.button("📦 一鍵載入預設對應"):
            stats = pfseed.seed_payment_aliases(force=False)
            n = stats.get('inserted', stats.get('count', 0)) \
                if isinstance(stats, dict) else 0
            st.success(f"✅ 已載入預設對應（{n} 條）")
            st.rerun()
    with al_c2:
        if st.button("🔄 重設為預設值（會刪掉自訂）",
                     type="secondary"):
            stats = pfseed.reset_payment_aliases_to_defaults()
            if isinstance(stats, dict):
                st.warning(
                    f"⚠️ 已重設！刪 {stats.get('deleted', 0)} 條、"
                    f"新增 {stats.get('inserted', 0)} 條"
                )
            else:
                st.warning("⚠️ 已重設為預設值")
            st.rerun()

    with st.expander("➕ 新增對應"):
        with st.form("alias_form"):
            accs = pfdb.list_accounts(account_type="asset") + \
                   pfdb.list_accounts(account_type="liability")
            acc_opts = {f"{a['code']} - {a['name']}": a["code"]
                        for a in accs}
            kw = st.text_input("關鍵字（會用 LIKE 模糊匹配）",
                                placeholder="例：PayMe / HSBC / Visa")
            acc_label = st.selectbox("對應到帳戶",
                                      list(acc_opts.keys()))
            al_notes = st.text_input("備註（選填）", "")
            if st.form_submit_button("💾 新增對應", type="primary"):
                if kw.strip():
                    try:
                        pfdb.add_payment_alias(
                            kw.strip(), acc_opts[acc_label],
                            al_notes or None)
                        st.success(
                            f"✅ {kw} → {acc_opts[acc_label]}")
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))

# ============ Tab 3: 期間鎖定 ============
with tab3:
    st.caption(
        "鎖定的月份不能新增 / 修改 / 刪除分錄，避免月結後資料變動。"
        "建議每月月結後鎖定上月。"
    )

    closed = pfdb.list_closed_periods()
    if closed:
        df_cl = pd.DataFrame([
            {
                "期間": cp["period"],
                "鎖定時間": cp.get("closed_at") or "—",
                "鎖定者": cp.get("closed_by") or "—",
                "備註": cp.get("notes") or "",
            }
            for cp in closed
        ])
        st.dataframe(df_cl, hide_index=True, use_container_width=True)
    else:
        st.info("尚未鎖定任何期間。所有月份均可自由編輯。")

    st.divider()
    pc1, pc2 = st.columns(2)

    with pc1:
        st.markdown("**🔒 鎖定一個期間**")
        with st.form("close_form"):
            from datetime import date as _d
            period_to_close = st.text_input(
                "期間 (YYYY-MM)",
                value=(_d.today().replace(day=1).strftime("%Y-%m"))
            )
            cl_notes = st.text_input("備註", "月結")
            if st.form_submit_button("🔒 確認鎖定", type="primary"):
                try:
                    pfdb.close_period(period_to_close,
                                        notes=cl_notes or None)
                    st.success(f"✅ 已鎖定 {period_to_close}")
                    st.rerun()
                except Exception as ex:
                    st.error(str(ex))

    with pc2:
        st.markdown("**🔓 重開（解鎖）期間**")
        if closed:
            periods = [cp["period"] for cp in closed]
            with st.form("reopen_form"):
                period_to_reopen = st.selectbox("選擇要解鎖的期間",
                                                  periods)
                if st.form_submit_button("🔓 確認解鎖",
                                          type="secondary"):
                    try:
                        pfdb.reopen_period(period_to_reopen)
                        st.warning(f"⚠️ 已解鎖 {period_to_reopen}")
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))
        else:
            st.caption("（目前沒有鎖定的期間）")

# ============ Tab 4: 專案管理 ============
with tab4:
    st.caption("建立專案以追蹤特定開支（例如：旅行、裝修、副業）")

    projects = pfdb.list_projects()
    if projects:
        df_pj = pd.DataFrame([
            {
                "ID": p["project_id"],
                "圖示": p.get("icon") or "🎯",
                "名稱": p["name"],
                "狀態": p.get("status") or "active",
                "預算 (HKD)": p.get("total_budget") or 0,
                "開始日": p.get("start_date") or "—",
                "結束日": p.get("end_date") or "—",
                "說明": p.get("description") or "",
            }
            for p in projects
        ])
        sel_p = st.dataframe(df_pj, hide_index=True,
                              use_container_width=True,
                              on_select="rerun",
                              selection_mode="single-row",
                              column_config={
                                  "預算 (HKD)":
                                  st.column_config.NumberColumn(
                                      format="$%.2f"),
                              })
        if sel_p.selection.rows:
            pid = int(df_pj.iloc[sel_p.selection.rows[0]]["ID"])
            pcur = pfdb.get_project(pid)
            with st.expander(f"✏️ 編輯專案 #{pid}", expanded=True):
                with st.form(f"proj_edit_{pid}"):
                    p_name = st.text_input("名稱",
                                            pcur.get("name", ""))
                    p_status = st.selectbox(
                        "狀態", ["active", "completed", "archived"],
                        index=["active", "completed", "archived"].index(
                            pcur.get("status") or "active"))
                    p_budget = st.number_input(
                        "預算（HKD）",
                        value=float(pcur.get("total_budget") or 0),
                        format="%.2f", min_value=0.0)
                    p_icon = st.text_input("圖示 emoji",
                                            pcur.get("icon") or "🎯")
                    p_desc = st.text_area(
                        "說明",
                        pcur.get("description") or "")
                    ec1, ec2 = st.columns(2)
                    if ec1.form_submit_button("💾 儲存",
                                                type="primary"):
                        pfdb.update_project(
                            pid, name=p_name, status=p_status,
                            total_budget=p_budget, icon=p_icon,
                            description=p_desc)
                        st.success("✅ 已更新")
                        st.rerun()
                    if ec2.form_submit_button("🗑️ 刪除",
                                                type="secondary"):
                        pfdb.delete_project(pid)
                        st.success("已刪除")
                        st.rerun()
    else:
        st.info("尚未建立任何專案。")

    st.divider()
    with st.expander("➕ 新增專案"):
        with st.form("new_proj"):
            np_name = st.text_input("專案名稱",
                                      placeholder="例：京都旅行 2026")
            np_icon = st.text_input("圖示 emoji", "🎯")
            np_budget = st.number_input("預算（HKD，選填）",
                                          value=0.0, format="%.2f")
            np_desc = st.text_area("說明（選填）", "")
            if st.form_submit_button("✨ 建立專案", type="primary"):
                if np_name.strip():
                    pid = pfdb.create_project(
                        np_name.strip(),
                        description=np_desc or None,
                        total_budget=np_budget if np_budget > 0
                                     else None,
                        icon=np_icon or "🎯")
                    st.success(f"✅ 建立 #{pid}：{np_name}")
                    st.rerun()
                else:
                    st.error("名稱不能為空")
