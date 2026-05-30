"""報銷追蹤 — 未報銷 / 已報銷 KPI + 待處理清單 + 一鍵收款"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd

from streamlit_app._common import (C, app_header, init_dbs, kpi_card,
                                      render_subpage_nav)

st.set_page_config(
    page_title="報銷追蹤", page_icon="🏢", layout="wide",
    initial_sidebar_state="expanded",
)
init_dbs()

app_header("個人記賬", "🏢",
           "公司報銷單據總覽 · 待收款清單 · 一鍵標記已收款")
render_subpage_nav("ledger")

import database as invdb
from personal_finance import db as pfdb, posting as pfpost
import cached_pfr

# ============ 🚀 並行 fetch 報銷追蹤所有資料 ============
if True:   # ⚡ 移除 spinner（cache hit 即時，避免閃動）
    _bundle = cached_pfr.fetch_reimbursement_bundle()
summary = _bundle["summary"]
all_company = _bundle["company_invoices"]
_asset_accs = _bundle["asset_accounts"]

c1, c2, c3, c4 = st.columns(4)
kpi_card(c1, "🏢 待報銷金額",
         summary["company_pending"], C["warning"], "🏢")
kpi_card(c2, "✅ 已收款金額",
         summary["company_reimbursed"], C["success"], "✅")
kpi_card(c3, "🧾 可扣稅總額",
         summary["tax_deductible_total"], C["info"], "🧾")
kpi_card(c4, "👤 私人開支",
         summary["personal_total"], C["accent"], "👤")

st.write("")

# ============ Tabs ============
tab1, tab2 = st.tabs(["⏳ 待收款清單", "✅ 已收款歷史"])

# 從 bundle 拆分 pending / done
pending = [i for i in all_company if not i.get("reimbursed")]
done = [i for i in all_company if i.get("reimbursed")]

# === Tab 1：待收款清單 ===
with tab1:
    if not pending:
        st.success("🎉 太好了！目前沒有待收款的報銷單據。")
    else:
        st.caption(
            f"📋 共 {len(pending)} 張待收款（合計 "
            f"${summary['company_pending']:,.2f}）"
        )

        # 顯示資料表
        df = pd.DataFrame([
            {
                "ID": inv["id"],
                "日期": inv.get("purchase_date") or "—",
                "商戶": inv.get("store_name") or "—",
                "類別": inv.get("category") or "—",
                "金額": inv.get("total_amount") or 0,
                "幣別": inv.get("currency") or "HKD",
                "墊支方式": inv.get("payment_method") or "—",
            }
            for inv in pending
        ])
        selected = st.dataframe(
            df, hide_index=True, use_container_width=True,
            column_config={
                "金額": st.column_config.NumberColumn(format="$%.2f"),
            },
            on_select="rerun", selection_mode="single-row",
        )

        # === 收款表單（如有選取單據）===
        if selected.selection.rows:
            idx = selected.selection.rows[0]
            sel_id = int(df.iloc[idx]["ID"])
            sel_inv = invdb.get_invoice(sel_id)

            st.divider()
            st.subheader(
                f"💰 標記 #{sel_id} 已收款"
                f"（{sel_inv.get('store_name', '?')} · "
                f"${sel_inv.get('total_amount', 0):,.2f}）"
            )

            # 選擇收款帳戶（級聯：父 → 子）
            from streamlit_app._common import cascade_account_picker
            rc1, rc2 = st.columns([2, 1])
            with rc1:
                st.markdown("**💳 收款入哪個帳戶？**")
                received_acc_code = cascade_account_picker(
                    "收款", account_types=["asset"],
                    key_prefix=f"ar_acc_{sel_id}",
                )
            with rc2:
                from datetime import date as _d
                rec_date = st.date_input("📅 收款日期", _d.today(),
                                          key=f"ar_date_{sel_id}")

            if st.button("✅ 確認收款並入賬", type="primary",
                         key=f"ar_btn_{sel_id}"):
                if not received_acc_code:
                    st.error("請選擇收款帳戶")
                else:
                    try:
                        receive_id = pfpost.mark_reimbursement_received(
                            invoice_id=sel_id,
                            received_account=received_acc_code,
                            received_date=rec_date.isoformat(),
                        )
                        invdb.toggle_reimbursed(sel_id)
                        st.success(
                            f"✅ 已收款並入賬！分錄 #{receive_id} "
                            f"（Dr {received_acc_code} "
                            f"/ Cr AR_REIMBURSE）"
                        )
                        st.rerun()
                    except Exception as ex:
                        st.error(f"❌ 收款失敗：{ex}")

# === Tab 2：已收款歷史 ===
with tab2:
    if not done:
        st.info("尚無已收款紀錄。")
    else:
        st.caption(
            f"📜 共 {len(done)} 張已收款（合計 "
            f"${summary['company_reimbursed']:,.2f}）"
        )
        df_done = pd.DataFrame([
            {
                "ID": inv["id"],
                "日期": inv.get("purchase_date") or "—",
                "商戶": inv.get("store_name") or "—",
                "類別": inv.get("category") or "—",
                "金額": inv.get("total_amount") or 0,
                "幣別": inv.get("currency") or "HKD",
                "已收款": "✅",
            }
            for inv in done
        ])
        st.dataframe(
            df_done, hide_index=True, use_container_width=True,
            column_config={
                "金額": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

        # 取消已收款
        st.divider()
        with st.expander("↩️ 將某張單標記回「未收款」（撤銷）"):
            ids = [str(i["id"]) for i in done]
            if ids:
                undo_id = st.selectbox("選擇要撤銷的 invoice ID", ids,
                                        key="undo_select")
                if st.button("⚠️ 撤銷已收款狀態", type="secondary"):
                    try:
                        invdb.toggle_reimbursed(int(undo_id))
                        st.warning(
                            f"已撤銷 #{undo_id}。"
                            f"⚠️ 注意：原本的收款分錄不會自動刪除，"
                            f"如需取消請至「💰 個人記賬」手動刪除。"
                        )
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))
