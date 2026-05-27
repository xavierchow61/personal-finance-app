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

tab0, tab1, tab2, tab3, tab4 = st.tabs([
    "📖 使用教學",
    "💱 外幣匯率",
    "🔗 付款方式對應",
    "🔒 期間鎖定",
    "🎯 專案管理",
])

# ============ Tab 0: 使用教學 ============
with tab0:
    # === 歡迎卡 ===
    st.markdown(
        """
        <div style="background:linear-gradient(135deg,
            rgba(0,166,224,0.15) 0%,
            rgba(255,199,0,0.12) 100%);
            border:2px solid rgba(0,166,224,0.3);
            border-radius:18px;padding:1.4rem 1.6rem;
            margin-bottom:1.2rem;
            box-shadow:0 6px 20px rgba(0,120,186,0.15);">
            <h2 style="color:#0078BA;margin:0 0 0.5rem 0;
                font-size:1.6rem;font-weight:700;">
                🎉 歡迎使用「哆啦理財」
            </h2>
            <p style="color:#1A1A2E;margin:0;line-height:1.6;
                font-size:0.95rem;">
                本系統整合 <b>AI 智能單據提取</b>、
                <b>雙式記賬</b>、<b>預算追蹤</b>、
                <b>公司報銷</b>等功能，
                讓您輕鬆管理個人財務。
                以下為各項主要功能的使用說明 ——
                建議首次使用時依序閱讀。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # === Step-by-step 教學（用 expander）===
    with st.expander("📤 第一步：提取單據", expanded=True):
        st.markdown(
            """
            1. 進入左側「**提取單據**」頁面
            2. 將收據圖片或 PDF **拖曳**至上傳區，
               或按按鈕逐個選擇檔案
            3. 勾選「**自動寫入個人記賬**」可同步入賬
            4. 按「**🚀 開始提取**」按鈕

            ✨ 系統將自動辨識：
            - 商戶名稱、購買日期、總金額、幣別
            - 消費類別（餐飲、交通、超市等）
            - 付款方式（自動對應至您的帳戶）
            - 自動跳過重複的單據
            """
        )

    with st.expander("📋 第二步：核對與編輯單據"):
        st.markdown(
            """
            1. 進入「**單據紀錄**」頁面查閱所有單據
            2. 可依商戶名稱、類別、報銷狀態等**篩選**
            3. **點選任一單據**可進入編輯介面
            4. 右側會顯示原始單據**圖片預覽**
            5. 可修改商戶、金額、類別、付款方式、報銷狀態等
            6. 按「**💾 儲存修改**」會自動重新入賬

            ⚠️ 若修改了「類型」、金額、類別或付款方式，
            系統會自動刪除原分錄並重新建立。
            """
        )

    with st.expander("💰 第三步：管理帳目（個人記賬）"):
        st.markdown(
            """
            本系統採用**雙式記賬法**（Double-entry），
            每筆交易必有借方與貸方且金額相等。

            個人記賬頁面共三個分頁：

            **📜 交易紀錄**
            - 查閱最新 100 筆分錄
            - 可展開查看分錄詳情（借方/貸方）
            - 可刪除錯誤的分錄

            **🏦 帳戶總覽**
            - 查看所有帳戶當前餘額（已換算為 HKD）
            - 包含資產、負債、收入、支出四類帳戶

            **➕ 新增分錄**
            - 手動建立分錄
            - 適用於：薪金入賬、信用卡還款、帳戶轉移
            - 支援多幣別（自動套用最新匯率）
            """
        )

    with st.expander("🎯 第四步：設定預算"):
        st.markdown(
            """
            1. 進入「**預算與實績**」頁面
            2. 確認上方期間（預設為當月，YYYY-MM 格式）
            3. 展開下方「**➕ 設定或修改預算**」
            4. 為各消費類別輸入預算金額（留空表示不設定）
            5. 按「**💾 儲存全部預算**」

            📊 上方表格會即時顯示：
            - 各類別預算 vs 實績
            - 餘額（預算 − 實績）
            - 使用率進度條
            - **超支類別會以紅色警示**

            📈 頁面底部會顯示**過去 12 個月支出走勢圖**。
            """
        )

    with st.expander("📈 第五步：查看財務報表"):
        st.markdown(
            """
            「**財務報表**」頁面提供三類報表：

            **💰 收支表（P&L）**
            - 選擇期間（本月/上月/本年/上年/年初至今）
            - 顯示總收入、總支出、淨額
            - 收入與支出按類別細分

            **🏦 資產負債表**
            - 選擇截止日期
            - 顯示資產總額、負債總額、淨資產
            - 各帳戶餘額明細

            **⚖️ 期間對比**
            - 並排比較兩個期間
            - 顯示收入/支出/淨額的差異
            - 各類別細項對比與變化百分比
            """
        )

    with st.expander("🏢 第六步：公司報銷流程（重要）"):
        st.markdown(
            """
            若該筆消費是**為公司墊支**的款項，請依此流程：

            **A. 記錄報銷單據**
            1. 在提取單據時或之後，將「**類型**」改為「**公司報銷**」
            2. 系統會自動建立特殊分錄：
               - **Dr** AR_REIMBURSE（應收款）
               - **Cr** 您的付款帳戶（如 HSBC_VISA）
            3. **不會**計入您的個人開支

            **B. 收到公司還款後**
            1. 進入「**報銷追蹤**」頁面
            2. 上方可見 KPI：待報銷金額、已收款金額
            3. 在「**⏳ 待收款清單**」中選取單據
            4. 揀「**收款帳戶**」（如 HSBC_BANK）
            5. 按「**✅ 確認收款並入賬**」
            6. 系統自動建立沖銷分錄：
               - **Dr** HSBC_BANK
               - **Cr** AR_REIMBURSE

            ⏪ 如需撤銷已收款狀態，可至「**已收款歷史**」分頁。
            """
        )

    with st.expander("⚙️ 進階設定說明"):
        st.markdown(
            """
            **💱 外幣匯率**
            - 設定 USD、JPY、CNY 等對 HKD 的匯率
            - 影響多幣別記賬與財務報表的金額換算
            - 可同一幣別設定多個生效日期

            **🔗 付款方式對應**
            - 將 AI 識別的字眼對應至實際帳戶
            - 例：「PayMe」→ PAYME 帳戶
            - 可一鍵載入預設對應，或新增自訂規則

            **🔒 期間鎖定**
            - 月結後鎖定該月份，防止誤改舊資料
            - 鎖定後該月份的分錄不能新增/修改/刪除
            - 如需修改可隨時解鎖

            **🎯 專案管理**
            - 為旅行、裝修、副業等項目建立專案
            - 可設定專案預算、開始/結束日期
            - 將分錄關聯至專案，方便追蹤
            """
        )

    with st.expander("💡 實用小貼士"):
        st.markdown(
            """
            - 📑 **重複單據自動跳過** — 同檔案、同日期+商戶+金額會被識別
            - 📄 **PDF 多頁** 會全部讀取（最多 10 頁）
            - 🖼️ 支援格式：JPG、JPEG、PNG、BMP、WEBP、TIFF、PDF
            - 💾 所有資料儲存於本機 SQLite（雲端版用 Supabase）
            - ⚡ 介面卡片可滑鼠**懸停**查看微動畫
            - 🔍 單據紀錄頁可用搜尋框找特定商戶或備註
            - 📊 匯出 Excel 會含 Dashboard 圖表 + 報銷專屬分頁
            """
        )

    # === 底部：聯絡資訊卡 ===
    st.markdown(
        """
        <div style="background:rgba(255,255,255,0.92);
            border:2px solid rgba(255,199,0,0.4);
            border-radius:16px;padding:1.2rem 1.4rem;
            margin-top:1rem;text-align:center;
            box-shadow:0 6px 18px rgba(255,199,0,0.15);">
            <div style="color:#0078BA;font-size:1.1rem;
                font-weight:700;margin-bottom:0.4rem;">
                🌟 開始使用吧！
            </div>
            <p style="color:#1A1A2E;margin:0;
                font-size:0.9rem;line-height:1.6;">
                建議先從「<b>📤 提取單據</b>」上傳一張收據試試看，
                系統會在數秒內為您完成提取與分類，
                並自動寫入您的個人記賬。
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
